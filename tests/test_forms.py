from django import forms
from django.test import TestCase
from dynamic_forms import DynamicField, DynamicFormMixin


class ContextTestCase(TestCase):
    class TestForm(DynamicFormMixin, forms.Form):
        pass

    def test_context(self):
        form = self.TestForm(context={"key": "value"})
        self.assertEqual(form.context, {"key": "value"})


class FieldArgumentPassedFromViewTestCase(TestCase):
    class TestForm(DynamicFormMixin, forms.Form):
        field_1 = DynamicField(
            forms.ChoiceField,
            choices=lambda form: form.context["choices"],
        )

    def test_field_argument_passed_from_view(self):
        form = self.TestForm(context={"choices": [("a", "A"), ("b", "B")]})
        self.assertEqual(form.fields["field_1"].choices, [("a", "A"), ("b", "B")])


class FieldArgumentFromOtherFieldTestCase(TestCase):
    class TestForm(DynamicFormMixin, forms.Form):
        label_for_field = forms.CharField(initial="initial label")
        field = DynamicField(
            forms.CharField,
            label=lambda form: form["label_for_field"].value().upper(),
        )

    def test_field_argument_from_other_field_initial(self):
        form = self.TestForm()
        self.assertEqual(form["field"].label, "INITIAL LABEL")

    def test_field_argument_from_other_field_value(self):
        form = self.TestForm({"label_for_field": "some label"})
        self.assertEqual(form["field"].label, "SOME LABEL")


class IncludeTestCase(TestCase):
    class TestForm(DynamicFormMixin, forms.Form):
        field_1 = forms.CharField()
        field_2 = DynamicField(
            forms.CharField,
            include=lambda form: form["field_1"].value() == "YES",
        )

    def test_field_included(self):
        form = self.TestForm({"field_1": "YES"})
        self.assertTrue("field_2" in form.fields)

    def test_field_not_included(self):
        form = self.TestForm({"field_1": "NO"})
        self.assertFalse("field_2" in form.fields)
