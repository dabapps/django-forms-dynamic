django-forms-dynamic
====================

**Resolve form field arguments dynamically when a form is instantiated, not when it's declared.**

Tested against Django 2.2, 3.2 and 4.0 on Python 3.6, 3.7, 3.8, 3.9 and 3.10

![Build Status](https://github.com/dabapps/django-forms-dynamic/workflows/CI/badge.svg)
[![pypi release](https://img.shields.io/pypi/v/django-forms-dynamic.svg)](https://pypi.python.org/pypi/django-forms-dynamic)

### Installation

Install from PyPI

    pip install django-forms-dynamic

## Usage

### Passing arguments to form fields from the view

The standard way to change a Django form's fields at runtime is override the form's `__init__` method, pass in any values you need from the view, and poke around in `self.fields`:

```python
class SelectUserFromMyTeamForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none())

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team")
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = User.objects.filter(team=team)
```

```python
def select_user_view(request):
    form = SelectUserFromMyTeamForm(team=request.user.team)
    return render("form.html", {"form": form})
```

This works, but it doesn't scale very well to more complex requirements. It also feels messy: Django forms are intended to be declarative, and this is very much procedural code.

With `django-forms-dynamic`, we can improve on this approach. We need to do two things:

1. Add the `DynamicFormMixin` to your form class (before `forms.Form`).
2. Wrap any field that needs dynamic behaviour in a `DynamicField`.

The first argument to the `DynamicField` constructor is the field _class_ that you are wrapping (eg `forms.ModelChoiceField`). All other arguments (with one special-cased exception detailed below) are passed along to the wrapped field when it is created.

But there's one very important difference: **any argument that would normally be passed to the field constructor can optionally be a _callable_**. If it is a callable, it will be called _when the form is being instantiated_ and it will be passed the form _instance_ as an argument. The value returned by this callable will then be passed into to the field's constructor as usual.

Before we see a code example, there's one further thing to note: instead of passing arbitrary arguments (like `team` in the example above) into the form's constructor in the view, we borrow a useful idiom from Django REST framework serializers and instead pass a _single_ argument called `context`, which is a dictionary that can contain any values you need from the view. This is attached to the form as `form.context`.

Here's how the code looks now:

```python
from dynamic_forms import DynamicField, DynamicFormMixin


class SelectUserFromMyTeamForm(DynamicFormMixin, forms.Form):
    user = DynamicField(
        forms.ModelChoiceField,
        queryset=lambda form: User.objects.filter(team=form.context["team"]),
    )
```

```python
def select_user_view(request):
    form = SelectUserFromMyTeamForm(context={"team": request.user.team})
    return render("form.html", {"form": form})
```

This is much nicer!

## Truly dynamic forms with XHR

But let's go further. Once we have access to the `form`, we can make forms truly dynamic by configuring fields based on the values of _other_ fields. This doesn't really make sense in the standard Django request/response approach, but it _does_ make sense when we bring JavaScript into the equation. A form can be loaded from the server multiple times (or in multiple pieces) by making XHR requests from JavaScript code running in the browser.

Implementing this "from scratch" in JavaScript is left as an exercise for the reader. Instead, let's look at how you might do this using some modern "low JavaScript" frameworks.

### [HTMX](https://htmx.org/)

To illustrate the pattern we're going to use one of the examples from the HTMX documentation: "Cascading Selects". This is where the options available in one `<select>` depend on the value chosen in another `<select>`. See [the HTMX docs page](https://htmx.org/examples/value-select/) for full details and a working example.

How would we implement the backend of this using `django-forms-dynamic`?

First, let's have a look at the form:

```python
class MakeAndModelForm(DynamicFormMixin, forms.Form):
    MAKE_CHOICES = [
        ("audi", "Audi"),
        ("toyota", "Toyota"),
        ("bmw", "BMW"),
    ]

    MODEL_CHOICES = {
        "audi": [
            ("a1", "A1"),
            ("a3", "A3"),
            ("a6", "A6"),
        ],
        "toyota": [
            ("landcruiser", "Landcruiser"),
            ("tacoma", "Tacoma"),
            ("yaris", "Yaris"),
        ],
        "bmw": [
            ("325i", "325i"),
            ("325ix", "325ix"),
            ("x5", "X5"),
        ],
    }

    make = forms.ChoiceField(
        choices=MAKE_CHOICES,
        initial="audi",
    )
    model = DynamicField(
        forms.ChoiceField,
        choices=lambda form: form.MODEL_CHOICES[form["make"].value()],
    )
```

The key bit is right at the bottom. We're using a lambda function to load the choices for the `model` field based on the currently selected value of the `make` field. When the form is first shown to the user, `form["make"].value()` will be `"audi"`: the `initial` value supplied to the `make` field. After the form is bound, `form["make"].value()` will return whatever the user selected in the `make` dropdown.

HTMX tends to encourage a pattern of splitting your UI into lots of small endpoints that return fragments of HTML. So we need two views: one to return the entire form on first page load, and one to return _just_ the HTML for the `model` field. The latter will be loaded whenever the `make` field changes, and will return the available `models` for the chosen `make`.

Here are the two views:

```python
def htmx_form(request):
    form = MakeAndModelForm()
    return render(request, "htmx.html", {"form": form})


def htmx_models(request):
    form = MakeAndModelForm(request.GET)
    return HttpResponse(form["model"])
```

Remember that the string representation of `form["model"]` (the bound field) is the HTML for the `<select>` element, so we can return this directly in the `HttpResponse`.

These can be wired up to URLs like this:

```python
urlpatterns = [
    path("htmx-form/", htmx_form),
    path("htmx-form/models/", htmx_models),
]
```

And finally, we need a template. We're using [django-widget-tweaks](https://github.com/jazzband/django-widget-tweaks) to add the necessary `hx-` attributes to the `make` field right in the template.

```django
{% load widget_tweaks %}
<!DOCTYPE html>

<html>
  <head>
    <script src="https://unpkg.com/htmx.org@1.6.1"></script>
  </head>
  <body>
    <form method="POST">
      <h3>Pick a make/model</h3>
      {% csrf_token %}
      <div>
        {{ form.make.label_tag }}
        {% render_field form.make hx-get="/htmx-form/models/" hx-target="#id_model" %}
      </div>
      <div>
        {{ form.model.label_tag }}
        {{ form.model }}
      </div>
    </form>
  </body>
</html>
```

### [Unpoly](https://unpoly.com/)

Let's build exactly the same thing with Unpoly. Unpoly favours a slightly different philosophy: rather than having the backend returning HTML fragments, it tends to prefer the server to return full HTML pages with every XHR request, and "plucks out" the relevant element(s) and inserts them into the DOM, replacing the old ones.

When it comes to forms, Unpoly uses a special attribute `[up-validate]` to mark fields which, when changed, should trigger the form to be submitted and re-validated. [The docs for `[up-validate]`](https://unpoly.com/input-up-validate) also describe it as "a great way to partially update a form when one field depends on the value of another field", so this is what we'll use to implement our cascading selects.

The form is exactly the same as the HTMX example above. But this time, we only need one view!

```python
def unpoly_form(request):
    form = MakeAndModelForm(request.POST or None)
    return render(request, "unpoly.html", {"form": form})
```

```python
urlpatterns = [
    path("unpoly-form/", unpoly_form),
]
```

And the template is even more simple:

```django
{% load widget_tweaks %}
<!DOCTYPE html>

<html>
  <head>
    <script src="https://unpkg.com/unpoly@2.5.0/unpoly.min.js"></script>
  </head>
  <body>
    <form method="POST">
      <h3>Pick a make/model</h3>
      {% csrf_token %}
      <div>
        {{ form.make.label_tag }}
        {% render_field form.make up-validate="form" %}
      </div>
      <div>
        {{ form.model.label_tag }}
        {{ form.model }}
      </div>
    </form>
  </body>
</html>
```

## The `include` argument

There's one more feature we might need: what if we want to remove a field from the form entirely unless another field has a particular value? To accomplish this, the `DynamicField` constructor takes one special argument that isn't passed along to the constructor of the wrapped field: `include`. Just like any other argument, this can be a callable that is passed the form instance, and it should return a boolean: `True` if the field should be included in the form, `False` otherwise. Here's an example:

```python
class CancellationReasonForm(DynamicFormMixin, forms.Form):
    CANCELLATION_REASONS = [
        ("too-expensive", "Too expensive"),
        ("too-boring", "Too boring"),
        ("other", "Other"),
    ]

    cancellation_reason = forms.ChoiceField(choices=CANCELLATION_REASONS)
    reason_if_other = DynamicField(
        forms.CharField,
        include=lambda form: form["cancellation_reason"].value() == "other",
    )
```

## Known gotcha: callable arguments

One thing that might catch you out: if the object you're passing in to your form field's constructor is _already_ a callable, you will need to wrap it in another callable that takes the `form` argument and returns the _actual_ callable you want to pass to the field.

This is most likely to crop up when you're passing a custom widget class, because classes are callable:

```python
class CancellationReasonForm(DynamicFormMixin, forms.Form):
    ...  # other fields

    reason_if_other = DynamicField(
        forms.CharField,
        include=lambda form: form["cancellation_reason"].value() == "other",
        widget=lambda _: forms.TextArea,
    )
```

## Why the awkward name?

Because `django-dynamic-forms` was already taken.

## Code of conduct

For guidelines regarding the code of conduct when contributing to this repository please review [https://www.dabapps.com/open-source/code-of-conduct/](https://www.dabapps.com/open-source/code-of-conduct/)
