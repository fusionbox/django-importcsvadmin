import csv
from functools import update_wrapper

from django.conf.urls import url
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.generic.edit import FormView

from importcsvadmin.forms import CSVImportError, ImportCSVForm


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

        info = self.model._meta.app_label, self.model._meta.model_name

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
