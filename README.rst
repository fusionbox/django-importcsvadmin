=====================
django-importcsvadmin
=====================

Allow the user to import models from a CSV file in the django admin site.

Basic Usage
===========

To enable CSV import for a model, simply subclass `ImportCSVModelAdmin`,
set its `importer_class` to a `ModelForm` subclass, and register it as
the `ModelAdmin` for your model.

Each row of CSV data will be loaded into an `importer_class` form which must
have a `Meta.fields` attribute which matches the data and order of the
CSV file.

The entire CSV import operation will be wrapped in an atomic transaction, and
will only write to the database if all rows pass validation.

Basic example::

  from django.contrib import admin
  from django.forms import ModelForm

  from importcsvadmin.admin import ImportCSVModelAdmin

  from my_app.models import MyModel


  class MyAdminImporter(ModelForm):
      class Meta:
          model = MyModel
          fields = ('first_field', 'second_field', 'third_field')


  class MyAdminForm(ModelForm):
      class Meta:
          model = MyModel
          fields = ('first_field', 'second_field', 'third_field')


  class MyAdmin(ImportCSVModelAdmin):
      importer_class = MyAdminImporter
      form = MyAdminForm


  admin.site.register(MyModel, MyAdmin)
