from django import forms

__version__ = "1.0.0"


def call_if_callable(value, *args, **kwargs):
    return value(*args, **kwargs) if callable(value) else value


class DynamicField(forms.Field):
    def __init__(self, field_class, *args, **kwargs):
        self.field_class = field_class
        self.args = args
        self.kwargs = kwargs
        self.include = self.kwargs.pop("include", True)
        super().__init__()

    def make_real_field(self, form):
        return self.field_class(
            *(call_if_callable(arg, form) for arg in self.args),
            **{name: call_if_callable(arg, form) for name, arg in self.kwargs.items()}
        )

    def should_be_included(self, form):
        return call_if_callable(self.include, form)


class DynamicFormMixin:
    def __init__(self, *args, **kwargs):
        self.context = kwargs.pop("context", None)
        super().__init__(*args, **kwargs)

        for name, field in list(self.fields.items()):
            if isinstance(field, DynamicField):
                if field.should_be_included(self):
                    self.fields[name] = field.make_real_field(self)
                else:
                    del self.fields[name]
