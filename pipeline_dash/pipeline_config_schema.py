import itertools
from types import NoneType

import flatdict  # type: ignore
from cerberus import rules_set_registry, Validator  # type: ignore


def check_pipeline_setting(field, value, error):
    setting_fields = {
        "label": {
            "key": ("$label",),
            "type": str,
        },
        "recurse": {
            "key": ("$recurse",),
            "type": bool,
        },
    }
    valid_keys = sorted(set(itertools.chain.from_iterable(f["key"] for f in setting_fields.values())))
    success = True
    if field in setting_fields["label"]["key"]:
        if not isinstance(value, setting_fields["label"]["type"]):
            error(
                field, f"Invalid value type for field '{field}': {type(value)} is not {setting_fields['label']['type']}"
            )
            success = False
    elif field in setting_fields["recurse"]["key"]:
        if not isinstance(value, setting_fields["recurse"]["type"]):
            error(
                field,
                f"Invalid value type for field '{field}': {type(value)} is not {setting_fields['recurse']['type']}",
            )
    else:
        error(field, f"Invalid settings field: '{field}' is not one of {valid_keys}")
        success = False
    return success


def check_pipeline(field, value, error):
    if field.startswith("$"):
        return check_pipeline_setting(field, value, error)

    valid_types = (list, dict, NoneType)
    if not isinstance(value, valid_types):
        error(
            field,
            f"Invalid value type for field '{field}': "
            f"'{type(value).__name__}' is not one of {[t.__name__ for t in valid_types]}",
        )


yaml_schema = {
    "name": {
        "type": "string",
        "required": False,
    },
    "url_translate": {
        "type": "dict",
        "required": False,
        "keysrules": {"type": "string"},
        "valuesrules": {"type": "string"},
    },
    "servers": {
        "type": "dict",
        "required": True,
        "keysrules": {"type": "string", "regex": "^https?://.*"},
        "valuesrules": {"schema": {"pipelines": "pipeline_rules"}},
    },
}

pipeline_rules = {
    "check_with": check_pipeline,
    "nullable": True,
    "keysrules": {
        "type": "string",
    },
    "valuesrules": "pipeline_rules",
}
rules_set_registry.add("pipeline_rules", pipeline_rules)


def validate_pipeline_config(yaml_dict: dict) -> None:
    """Throws SchemaError if validation fails"""
    v = Validator(schema=yaml_schema)
    if v.validate(yaml_dict):
        return

    flat_errors = flatdict.FlatterDict(v.errors, delimiter="::")
    for k, v in flat_errors.items():
        display_name = ":".join(k.split("::")[::2])
        print(f"{display_name}:\n\t{v}")
