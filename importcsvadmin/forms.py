import csv

from django.db import transaction
from django import forms
from django.forms.forms import NON_FIELD_ERRORS
from django.utils import six
from django.utils.translation import ugettext_lazy as _


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
                # Translators: "{row}", "{column}" and "{error}"
                # should not be translated
                fmt = _("Could not import row #{row}: {column} - {error}")
            else:
                # Translators: "{row}" and "{error}" should not be translated
                fmt = _("Could not import row #{row}: {error}")
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
