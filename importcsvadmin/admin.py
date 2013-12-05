import csv, sys
from functools import update_wrapper
from itertools import count

from django.conf.urls import url
from django.contrib import admin
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse
from django import forms
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.views.generic.edit import FormView


class ImportCSVForm(forms.Form):
    csv_file = forms.FileField(required=True, label=_('CSV File'))


class ImportCSVAdminView(FormView):
    form_class = ImportCSVForm
    model_admin = None

    def get_template_names(self):
        importcsv_template = self.model_admin.importcsv_template
        if importcsv_template is not None:
            return importcsv_template
        else:
            opts = self.model_admin.model._meta

            app_label = opts.app_label
            object_name = opts.object_name.lower()

            return [
                'admin/%s/%s/csv_import.html' % (app_label, object_name),
                'admin/%s/csv_import.html' % app_label,
                'admin/csv_import.html',
            ]

    def get_success_url(self):
        return reverse(self.model_admin.changelist_view)

    def form_valid(self, form):
        try:
            self.import_csv(form.cleaned_data['csv_file'])
        except ValueError:
            return self.form_invalid(form)
        return super(ImportCSVAdminView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(ImportCSVAdminView, self).get_context_data(**kwargs)
        context['opts'] = self.model_admin.model._meta
        return context

    @transaction.commit_on_success
    def import_csv(self, file_):
        reader = csv.reader(file_, dialect=self.model_admin.dialect)

        reader_iter = iter(six.moves.zip(count(start=1), reader))
        if self.model_admin.skip_firstline:
            six.advance_iterator(reader_iter)

        for i, row in reader_iter:
            try:
                self.process_row(row)
            except ValueError as e:
                messages.error(self.request, _("Couldn't process row #%d: %s") % (i, e.message))
                messages.error(self.request, _("Import has been canceled. Nothing was imported."))
                six.reraise(*sys.exc_info())

    def process_row(self, row):
        obj = self.model_admin.model()
        for data, mapping in six.moves.zip(row, self.model_admin.csv_mapping):
            if self.model_admin.dont_set_empty_fields and not data:
                continue
            if isinstance(mapping, six.string_types):
                setattr(obj, mapping, data)
            elif callable(mapping):
                mapping(obj, data)
            else:
                raise TypeError("Mapping must be a callable or a string")
        obj.save()


class ImportCSVModelAdmin(admin.ModelAdmin):
    importcsv_view_class = ImportCSVAdminView
    importcsv_template = None

    dialect = csv.excel
    skip_firstline = True
    dont_set_empty_fields = True

    @property
    def change_list_template(self):
        opts = self.model._meta
        return [
            'admin/%s/%s/change_list_csv.html' % (opts.app_label, opts.object_name.lower()),
            'admin/%s/change_list_csv.html' % opts.app_label,
            'admin/change_list_csv.html',
        ]

    def get_urls(self):
        # XXX: Shamelessly copied from django/contrib/admin/options.py
        def wrap(view):
            def wrapper(*args, **kwargs):
                return self.admin_site.admin_view(view)(*args, **kwargs)
            return update_wrapper(wrapper, view)

        info = self.model._meta.app_label, self.model._meta.module_name

        urlpatterns = super(ImportCSVModelAdmin, self).get_urls()

        extra_urls = [
            url(r'^import-csv/$',
                wrap(self.importcsv_view),
                name='%s_%s_importcsv' % info),
            url(r'^import-csv/template.csv$',
                wrap(self.download_csv_template),
                name='%s_%s_csvtemplate' % info),
        ]
        return extra_urls + urlpatterns

    @property
    def importcsv_view(self):
        return self.importcsv_view_class.as_view(model_admin=self)

    def download_csv_template(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachement; filename="template.csv"'

        writer = csv.writer(response, dialect=self.dialect)
        writer.writerow(self.csv_columns)

        return response

