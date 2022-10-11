from __future__ import annotations
from typing import TYPE_CHECKING, Callable, List, Tuple


try:
    import mypy.types
    from mypy.types import Type
    from mypy.plugin import Plugin, AnalyzeTypeContext
    from mypy.nodes import MypyFile, Import, Statement, AssignmentStmt, TupleExpr, NameExpr, CallExpr, MemberExpr, ImportFrom
    from mypy.build import PRI_MED

    _HookFunc = Callable[[AnalyzeTypeContext], Type]
    MYPY_EX: None | ModuleNotFoundError = None
except ModuleNotFoundError as ex:
    MYPY_EX = ex


if not TYPE_CHECKING and MYPY_EX is not None:  # Handle failure

    def plugin(version: str) -> type[_LazyLoaderPlugin]:
        """An entry-point for mypy."""
        raise MYPY_EX


else:
    def _is_attach_statement(d: Statement, import_name: str) -> bool:
        return (
            isinstance(d, AssignmentStmt)
            and isinstance(d.rvalue, CallExpr)
            and isinstance(d.rvalue.callee, MemberExpr)
            and d.rvalue.callee.name == "attach"
            and isinstance(d.rvalue.callee.expr, NameExpr)
            and d.rvalue.callee.expr.name == import_name
            # TODO! check that came from module lazy_load, but need to map import back
            # left values: __getattr__, __dir__, __all__ 
            and len(d.lvalues) == 1
            and isinstance(d.lvalues[0], TupleExpr)
            and len(d.lvalues[0].items) == 3
            # and all(isinstance(e, NameExpr) for e in d.lvalues[0].items)
            and (isinstance((e0 := d.lvalues[0].items[0]), NameExpr) and e0.name == "__getattr__")
            and (isinstance((e1 := d.lvalues[0].items[1]), NameExpr) and e1.name == "__dir__")
            and (isinstance((e2 := d.lvalues[0].items[2]), NameExpr) and e2.name == "__all__")
        )

    def _get_import(module: str, imports: list[tuple[str, None | str]]) -> ImportFrom:
        # Construct a new `from module import y` statement
        import_obj = ImportFrom(module, 0, names=imports)
        # import_obj.is_top_level = True

        return import_obj

    class _LazyLoaderPlugin(Plugin):
        # FIXME! this is the wrong hook b/c cannot insert imports
        def get_additional_deps(self, file: MypyFile) -> list[tuple[int, str, int]]:
            # Only work with __init__ files
            if not file.is_package_init_file():
                return []
            # Find any "import lazy_loader..." (not this skips "from lazy_loader import")
            elif not any(llimports := [m for m in file.imports if (isinstance(m, Import) and m.ids[0][0] == "lazy_loader")]):
                return []
            elif len(llimports) > 1:
                raise ValueError

            llimport = llimports[0]
            import_name = llimport.ids[0][1] if llimport.ids[0][1] is not None else llimport.ids[0][0]
            attachdefs = [d for d in file.defs if _is_attach_statement(d, import_name)]

            if len(attachdefs) > 1:
                raise ValueError
            elif not isinstance((attachdef := attachdefs[0]), AssignmentStmt):
                raise ValueError
            elif not isinstance(attachdef.rvalue, CallExpr):
                raise ValueError

            # submodules arg
            if "submodules" in attachdef.rvalue.arg_names:  # kwarg
                submodules = attachdef.rvalue.args[attachdef.rvalue.arg_names.index("submodules")]
            elif (len(attachdef.rvalue.args) > 1 and "submod_attrs" not in attachdef.rvalue.arg_names):  # arg
                submodules = attachdef.rvalue.args[1]
            else:
                submodules = None

            if "submod_attrs" in attachdef.rvalue.arg_names:  # kwarg
                submod_attrs = attachdef.rvalue.args[attachdef.rvalue.arg_names.index("submod_attrs")]
            elif len(attachdef.rvalue.args) > 2:  # arg
                submod_attrs = attachdef.rvalue.args[2]
            else:
                submod_attrs = None

            ret: list[tuple[int, str, int]] = []

            if submodules is not None:
                # TODO? actually insert the import line into the file
                # TODO! proper type narrow to make sure items exists and is iterable
                # file.imports.append(_get_import(file.fullname, [(n.value, n.value) for n in getattr(submodules, "items", ())]))
                # import pdb; pdb.set_trace()
                # ret.extend([(PRI_MED, n.value, -1) for n in getattr(submodules, "items", ())])


            # TODO! submod_attrs
            print(ret)

            return ret

    def plugin(version: str) -> type[_LazyLoaderPlugin]:
        """An entry-point for mypy."""
        return _LazyLoaderPlugin