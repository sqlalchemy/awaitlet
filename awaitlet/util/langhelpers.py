from __future__ import annotations

from functools import update_wrapper
import inspect
import typing
from typing import Any
from typing import Callable
from typing import cast
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import TypeVar
from typing import Union

_T = TypeVar("_T", bound=Any)
_T_co = TypeVar("_T_co", covariant=True)


class FullArgSpec(typing.NamedTuple):
    args: List[str]
    varargs: Optional[str]
    varkw: Optional[str]
    defaults: Optional[Tuple[Any, ...]]
    kwonlyargs: List[str]
    kwonlydefaults: Dict[str, Any]
    annotations: Dict[str, Any]


def _pytest_fn_decorator(target):
    """Port of langhelpers.decorator with pytest-specific tricks."""

    def _exec_code_in_env(code, env, fn_name):
        # note this is affected by "from __future__ import annotations" at
        # the top; exec'ed code will use non-evaluated annotations
        # which allows us to be more flexible with code rendering
        # in format_argpsec_plus()
        exec(code, env)
        return env[fn_name]

    def decorate(fn, add_positional_parameters=()):
        spec = inspect.getfullargspec(fn)
        if add_positional_parameters:
            spec.args.extend(add_positional_parameters)

        metadata = dict(
            __target_fn="__target_fn", __orig_fn="__orig_fn", name=fn.__name__
        )
        metadata.update(_format_argspec_plus(spec, grouped=False))
        code = (
            """\
def %(name)s%(grouped_args)s:
    return %(__target_fn)s(%(__orig_fn)s, %(apply_kw)s)
"""
            % metadata
        )
        decorated = _exec_code_in_env(
            code, {"__target_fn": target, "__orig_fn": fn}, fn.__name__
        )
        if not add_positional_parameters:
            decorated.__defaults__ = getattr(fn, "__func__", fn).__defaults__
            decorated.__wrapped__ = fn
            return update_wrapper(decorated, fn)
        else:
            # this is the pytest hacky part.  don't do a full update wrapper
            # because pytest is really being sneaky about finding the args
            # for the wrapped function
            decorated.__module__ = fn.__module__
            decorated.__name__ = fn.__name__
            if hasattr(fn, "pytestmark"):
                decorated.pytestmark = fn.pytestmark
            return decorated

    return decorate


def _format_argspec_plus(
    fn: Union[Callable[..., Any], FullArgSpec], grouped: bool = True
) -> Dict[str, Optional[str]]:
    """Returns a dictionary of formatted, introspected function arguments.

    A enhanced variant of inspect.formatargspec to support code generation.

    fn
       An inspectable callable or tuple of inspect getargspec() results.
    grouped
      Defaults to True; include (parens, around, argument) lists

    Returns:

    args
      Full inspect.formatargspec for fn
    self_arg
      The name of the first positional argument, varargs[0], or None
      if the function defines no positional arguments.
    apply_pos
      args, re-written in calling rather than receiving syntax.  Arguments are
      passed positionally.
    apply_kw
      Like apply_pos, except keyword-ish args are passed as keywords.
    apply_pos_proxied
      Like apply_pos but omits the self/cls argument

    Example::

      >>> format_argspec_plus(lambda self, a, b, c=3, **d: 123)
      {'grouped_args': '(self, a, b, c=3, **d)',
       'self_arg': 'self',
       'apply_kw': '(self, a, b, c=c, **d)',
       'apply_pos': '(self, a, b, c, **d)'}

    """
    spec: FullArgSpec | inspect.FullArgSpec
    if callable(fn):
        spec = inspect.getfullargspec(fn)
    else:
        spec = fn

    args = _inspect_formatargspec(*spec)

    apply_pos = _inspect_formatargspec(
        spec[0], spec[1], spec[2], None, spec[4]
    )

    if spec[0]:
        self_arg = spec[0][0]

        apply_pos_proxied = _inspect_formatargspec(
            spec[0][1:], spec[1], spec[2], None, spec[4]
        )

    elif spec[1]:
        # I'm not sure what this is
        self_arg = "%s[0]" % spec[1]

        apply_pos_proxied = apply_pos
    else:
        self_arg = None
        apply_pos_proxied = apply_pos

    num_defaults = 0
    if spec[3]:
        num_defaults += len(cast(Tuple[Any], spec[3]))
    if spec[4]:
        num_defaults += len(spec[4])

    name_args = spec[0] + spec[4]

    defaulted_vals: Union[List[str], Tuple[()]]

    if num_defaults:
        defaulted_vals = name_args[0 - num_defaults :]
    else:
        defaulted_vals = ()

    apply_kw = _inspect_formatargspec(
        name_args,
        spec[1],
        spec[2],
        defaulted_vals,
        formatvalue=lambda x: "=" + str(x),
    )

    if spec[0]:
        apply_kw_proxied = _inspect_formatargspec(
            name_args[1:],
            spec[1],
            spec[2],
            defaulted_vals,
            formatvalue=lambda x: "=" + str(x),
        )
    else:
        apply_kw_proxied = apply_kw

    if grouped:
        return dict(
            grouped_args=args,
            self_arg=self_arg,
            apply_pos=apply_pos,
            apply_kw=apply_kw,
            apply_pos_proxied=apply_pos_proxied,
            apply_kw_proxied=apply_kw_proxied,
        )
    else:
        return dict(
            grouped_args=args,
            self_arg=self_arg,
            apply_pos=apply_pos[1:-1],
            apply_kw=apply_kw[1:-1],
            apply_pos_proxied=apply_pos_proxied[1:-1],
            apply_kw_proxied=apply_kw_proxied[1:-1],
        )


def _formatannotation(annotation, base_module=None):
    """vendored from python 3.7"""

    if isinstance(annotation, str):
        return annotation

    if getattr(annotation, "__module__", None) == "typing":
        return repr(annotation).replace("typing.", "").replace("~", "")
    if isinstance(annotation, type):
        if annotation.__module__ in ("builtins", base_module):
            return repr(annotation.__qualname__)
        return annotation.__module__ + "." + annotation.__qualname__
    elif isinstance(annotation, typing.TypeVar):
        return repr(annotation).replace("~", "")
    return repr(annotation).replace("~", "")


def _inspect_formatargspec(
    args: List[str],
    varargs: Optional[str] = None,
    varkw: Optional[str] = None,
    defaults: Optional[Sequence[Any]] = None,
    kwonlyargs: Optional[Sequence[str]] = (),
    kwonlydefaults: Optional[Mapping[str, Any]] = {},
    annotations: Mapping[str, Any] = {},
    formatarg: Callable[[str], str] = str,
    formatvarargs: Callable[[str], str] = lambda name: "*" + name,
    formatvarkw: Callable[[str], str] = lambda name: "**" + name,
    formatvalue: Callable[[Any], str] = lambda value: "=" + repr(value),
    formatreturns: Callable[[Any], str] = lambda text: " -> " + str(text),
    formatannotation: Callable[[Any], str] = _formatannotation,
) -> str:
    """Copy formatargspec from python 3.7 standard library.

    Python 3 has deprecated formatargspec and requested that Signature
    be used instead, however this requires a full reimplementation
    of formatargspec() in terms of creating Parameter objects and such.
    Instead of introducing all the object-creation overhead and having
    to reinvent from scratch, just copy their compatibility routine.

    """

    kwonlydefaults = kwonlydefaults or {}
    annotations = annotations or {}

    def formatargandannotation(arg):
        result = formatarg(arg)
        if arg in annotations:
            result += ": " + formatannotation(annotations[arg])
        return result

    specs = []
    if defaults:
        firstdefault = len(args) - len(defaults)
    else:
        firstdefault = -1

    for i, arg in enumerate(args):
        spec = formatargandannotation(arg)
        if defaults and i >= firstdefault:
            spec = spec + formatvalue(defaults[i - firstdefault])
        specs.append(spec)

    if varargs is not None:
        specs.append(formatvarargs(formatargandannotation(varargs)))
    else:
        if kwonlyargs:
            specs.append("*")

    if kwonlyargs:
        for kwonlyarg in kwonlyargs:
            spec = formatargandannotation(kwonlyarg)
            if kwonlydefaults and kwonlyarg in kwonlydefaults:
                spec += formatvalue(kwonlydefaults[kwonlyarg])
            specs.append(spec)

    if varkw is not None:
        specs.append(formatvarkw(formatargandannotation(varkw)))

    result = "(" + ", ".join(specs) + ")"
    if "return" in annotations:
        result += formatreturns(formatannotation(annotations["return"]))
    return result
