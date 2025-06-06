from __future__ import annotations

from collections.abc import Iterable


class NameGenerator:
    """Utility for generating distinct C names from Python names.

    Since C names can't use '.' (or unicode), some care is required to
    make C names generated from Python names unique. Also, we want to
    avoid generating overly long C names since they make the generated
    code harder to read.

    Note that we don't restrict ourselves to a 32-character distinguishing
    prefix guaranteed by the C standard since all the compilers we care
    about at the moment support longer names without issues.

    For names that are exported in a shared library (not static) use
    exported_name() instead.

    Summary of the approach:

    * Generate a unique name prefix from suffix of fully-qualified
      module name used for static names. If only compiling a single
      module, this can be empty. For example, if the modules are
      'foo.bar' and 'foo.baz', the prefixes can be 'bar_' and 'baz_',
      respectively. If the modules are 'bar.foo' and 'baz.foo', the
      prefixes will be 'bar_foo_' and 'baz_foo_'.

    * Replace '.' in the Python name with '___' in the C name. (And
      replace the unlikely but possible '___' with '___3_'. This
      collides '___' with '.3_', but this is OK because names
      may not start with a digit.)

    The generated should be internal to a build and thus the mapping is
    arbitrary. Just generating names '1', '2', ... would be correct,
    though not very usable. The generated names may be visible in CPU
    profiles and when debugging using native debuggers.
    """

    def __init__(self, groups: Iterable[list[str]], *, separate: bool = False) -> None:
        """Initialize with a list of modules in each compilation group.

        The names of modules are used to shorten names referring to
        modules, for convenience. Arbitrary module
        names are supported for generated names, but uncompiled modules
        will use long names.

        If separate is True, assume separate compilation. This implies
        that we don't have knowledge of all sources that will be linked
        together. In this case we won't trim module prefixes, since we
        don't have enough information to determine common module prefixes.
        """
        self.module_map: dict[str, str] = {}
        for names in groups:
            if not separate:
                self.module_map.update(make_module_translation_map(names))
            else:
                for name in names:
                    self.module_map[name] = name + "."
        self.translations: dict[tuple[str, str], str] = {}
        self.used_names: set[str] = set()

    def private_name(self, module: str, partial_name: str | None = None) -> str:
        """Return a C name usable for a static definition.

        Return a distinct result for each (module, partial_name) pair.

        The caller should add a suitable prefix to the name to avoid
        conflicts with other C names. Only ensure that the results of
        this function are unique, not that they aren't overlapping with
        arbitrary names.

        If a name is not specific to any module, the module argument can
        be an empty string.
        """
        # TODO: Support unicode
        if partial_name is None:
            return exported_name(self.module_map[module].rstrip("."))
        if (module, partial_name) in self.translations:
            return self.translations[module, partial_name]
        if module in self.module_map:
            module_prefix = self.module_map[module]
        elif module:
            module_prefix = module + "."
        else:
            module_prefix = ""
        actual = exported_name(f"{module_prefix}{partial_name}")
        self.translations[module, partial_name] = actual
        return actual


def exported_name(fullname: str) -> str:
    """Return a C name usable for an exported definition.

    This is like private_name(), but the output only depends on the
    'fullname' argument, so the names are distinct across multiple
    builds.
    """
    # TODO: Support unicode
    return fullname.replace("___", "___3_").replace(".", "___")


def make_module_translation_map(names: list[str]) -> dict[str, str]:
    num_instances: dict[str, int] = {}
    for name in names:
        for suffix in candidate_suffixes(name):
            num_instances[suffix] = num_instances.get(suffix, 0) + 1
    result = {}
    for name in names:
        for suffix in candidate_suffixes(name):
            if num_instances[suffix] == 1:
                break
        # Takes the last suffix if none are unique
        result[name] = suffix
    return result


def candidate_suffixes(fullname: str) -> list[str]:
    components = fullname.split(".")
    result = [""]
    for i in range(len(components)):
        result.append(".".join(components[-i - 1 :]) + ".")
    return result
