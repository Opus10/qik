
<a id="pygraph"></a>

### Import Graph Dependencies

When depending on a Python module's import graph, any import, even inside of a `TYPE_CHECKING` block, will be included in the dependency graph. Similarly, any direct third-party import will be included as a distribution dependency. Disable this behavior with the `pygraph` config section:

```toml
[pygraph]
ignore-type-checking = true
ignore-pydists = true
```

!!! note

    Optional distributions that aren't installed in the virtual environment may lead to mapping and version resolution errors. See the troubleshooting section on [mapping modules to distributions](errors.md#graph0) and [overriding distribution versions](errors.md#dep0) for more information.

Qik does not discover dynamic imports such as django's [apps.get_model](https://docs.djangoproject.com/en/5.0/ref/applications/#django.apps.AppConfig.get_models). To ensure accuracy in your import graph, do either of:

- Add a standalone file (such as `qikimports.py`) with the non-dynamic imports.
- Do dynamic imports outside of `TYPE_CHECKING`. For example:

    ```
    from typing import TYPE_CHECKING

    from django.apps import apps

    if TYPE_CHECKING:
        # Qik will discover this import
        from my_app.models import MyModel
    else:
        # Do dynamic or lazy importing in the app
        MyModel = apps.get_model("my_app", "MyModel")
    ```