import csv
from functools import update_wrapper

from django.conf.urls import url
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponse
from django import forms
from django.forms.forms import NON_FIELD_ERRORS
from django.utils import six
from django.utils.translation import ugettext_lazy as _
from django.views.generic.edit import FormView


class CSVImportError(Exception):
    pass


class ImportCSVForm(forms.Form):
    csv_file = forms.FileField(required=True, label=_('CSV File'))
    has_headers = forms.BooleanField(
        label=_('Has headers'),
        help_text=_('Check this whether or not your CSV file '
                    'has a row with columns headers.'),
        initial=True,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.importer_class = kwargs.pop('importer_class')
        self.dialect = kwargs.pop('dialect')
        super(ImportCSVForm, self).__init__(*args, **kwargs)

    @transaction.commit_on_success
    def import_csv(self):
        try:
            reader = csv.DictReader(
                self.cleaned_data['csv_file'],
                fieldnames=self.importer_class._meta.fields,
                dialect=self.dialect,
            )

            reader_iter = enumerate(reader, 1)
            if self.cleaned_data['has_headers']:
                six.advance_iterator(reader_iter)

            self.process_csv(reader_iter)
            if not self.is_valid():
                raise CSVImportError()  # Abort the transaction
        except csv.Error as e:
            self.append_import_error(_("Bad CSV format"))
            raise CSVImportError()

    def process_csv(self, reader):
        for i, row in reader:
            self.process_row(i, row)

    def append_import_error(self, error, rownumber=None, column_name=None):
        if rownumber is not None:
            if column_name is not None:
                # Translators: "{row}" and "{error}" should not be translated
                fmt = _("Could not import row #{row}: {error}")
            else:
                # Translators: "{row}", "{column}" and "{error}"
                # should not be translated
                fmt = _("Could not import row #{row}: {column} - {error}")
        else:
            if column_name is not None:
                raise ValueError("Cannot raise a CSV import error on a specific "
                                 "column with no row number.")
            else:
                # Translators: "{error}" should not be translated
                fmt = _("Could not import the CSV document: {error}")

        if NON_FIELD_ERRORS not in self._errors:
            self._errors[NON_FIELD_ERRORS] = self.error_class()
        self._errors[NON_FIELD_ERRORS].append(
            fmt.format(error=error, row=rownumber, column=column_name))

    def process_row(self, i, row):
        importer = self.importer_class(data=row)
        if importer.is_valid():
            importer.save()
        else:
            for field, errors_list in six.iteritems(importer.errors):
                for error in errors_list:
                    if field == NON_FIELD_ERRORS:
                        self.append_import_error(
                            error=error,
                            rownumber=i,
                        )
                    else:
                        self.append_import_error(
                            error=error,
                            rownumber=i,
                            column_name=importer[field].label
                        )


class ImportCSVAdminView(FormView):
    model_admin = None

    def _get_meta(self):
        opts = self.model_admin.model._meta
        app_label = opts.app_label
        object_name = opts.object_name.lower()
        return (app_label, object_name)

    def get_template_names(self):
        importcsv_template = self.model_admin.importcsv_template
        if importcsv_template is not None:
            return importcsv_template
        else:
            app_label, object_name = self._get_meta()
            return [
                'admin/%s/%s/csv_import.html' % (app_label, object_name),
                'admin/%s/csv_import.html' % app_label,
                'admin/csv_import.html',
            ]

    def get_success_url(self):
        app_label, object_name = self._get_meta()
        return reverse('admin:%s_%s_changelist' % (app_label, object_name))

    def form_valid(self, form):
        try:
            form.import_csv()
        except CSVImportError:
            return self.form_invalid(form)
        return super(ImportCSVAdminView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(ImportCSVAdminView, self).get_context_data(**kwargs)
        context['opts'] = self.model_admin.model._meta
        return context

    def get_form_kwargs(self, **kwargs):
        kwargs = super(ImportCSVAdminView, self).get_form_kwargs(**kwargs)
        kwargs['importer_class'] = self.model_admin.importer_class
        kwargs['dialect'] = self.model_admin.dialect
        return kwargs

    def get_form_class(self, **kwargs):
        return self.model_admin.importcsv_form_class


class ImportCSVModelAdmin(admin.ModelAdmin):
    importcsv_view_class = ImportCSVAdminView
    importcsv_form_class = ImportCSVForm
    importcsv_template = None

    dialect = csv.excel
    skip_firstline = True

    @property
    def change_list_template(self):
        opts = self.model._meta
        return [
            'admin/%s/%s/change_list_csv.html' % (opts.app_label, opts.object_name.lower()),
            'admin/%s/change_list_csv.html' % opts.app_label,
            'admin/change_list_csv.html',
        ]

    def get_urls(self):
        def wrap(view):
            def wrapper(request, *args, **kwargs):
                if not self.has_add_permission(request):
                    raise PermissionDenied
                return self.admin_site.admin_view(view)(request, *args, **kwargs)
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
        def get_label(form, fname):
            field = form[fname]
            label = field.label
            if field.field.required:
                label = '%s*' % label
            return label

        importer = self.importer_class()

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="template.csv"'

        writer = csv.writer(response, dialect=self.dialect)

        fields = importer._meta.fields
        labels = [get_label(importer, fname) for fname in fields]
        writer.writerow(labels)

        return response
