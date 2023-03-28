# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Binds a python executable as a rez package.
"""
from __future__ import absolute_import
from rez.bind._utils import check_version, find_exe, extract_version, \
    make_dirs, log, run_python_command
from rez.package_maker import make_package
from rez.system import system
from rez.utils.lint_helper import env
from rez.utils.platform_ import platform_
import shutil
import os


def setup_parser(parser):
    parser.add_argument("--exe", type=str, metavar="PATH",
                        help="bind an interpreter other than the current "
                        "python interpreter")


def commands():
    noop = intersects(ephemerals.get_range('dcc_python', '0'), '1')
    if not noop:
        env.PATH.append('{this.root}/bin')


def post_commands():
    # these are the builtin modules for this python executable. If we don't
    # include these, some python behavior can be incorrect.
    import os
    import os.path

    noop = intersects(ephemerals.get_range('dcc_python', '0'), '1')
    if not noop:

        path = os.path.join(this.root, "python")  # noqa
        for dirname in os.listdir(path):
            path_ = os.path.join(path, dirname)
            env.PYTHONPATH.append(path_)


def bind(path, version_range=None, opts=None, parser=None):
    # find executable, determine version
    exepath = find_exe("python", opts.exe)
    code = "import sys; print('.'.join(str(x) for x in sys.version_info))"
    version = extract_version(exepath, ["-c", code])

    check_version(version, version_range)
    log("binding python: %s" % exepath)

    # find builtin modules
    builtin_paths = {}
    entries = [("lib", "os"), 
               ("extra", "setuptools")]

    for dirname, module_name in entries:
        success, out, err = run_python_command([
            "import %s" % module_name,
            "print(%s.__file__)" % module_name],
            exepath)

        if success:
            pypath = os.path.dirname(out)
            if os.path.basename(pypath) == module_name:
                pypath = os.path.dirname(pypath)

            if pypath not in builtin_paths.values():
                builtin_paths[dirname] = pypath

    # add DLLs
    basedir = os.path.dirname(exepath)
    if platform_.name == "windows":
        builtin_paths["DLLs"] = "%s/%s" % (basedir, "DLLs")

    # make the package
    #

    def make_root(variant, root):
        binpath = make_dirs(root, "bin")

        # vanilla rez symlinks the python exe but that didn't work on windows
        # so we copy the exe along with all the other files in the base dir
        for item in os.listdir(basedir):
            fullpath = os.path.join(basedir, item)
            if os.path.isfile(fullpath):
                shutil.copy(fullpath, binpath)

        if builtin_paths:
            pypath = make_dirs(root, "python")
            for dirname, srcpath in builtin_paths.items():
                destpath = os.path.join(pypath, dirname)
                log("Copying builtins from %s to %s..." % (srcpath, destpath))
                shutil.copytree(srcpath, destpath)

    with make_package("python", path, make_root=make_root) as pkg:
        pkg.version = version
        pkg.tools = ["python"]
        pkg.commands = commands
        pkg.variants = [system.variant]

        if builtin_paths:
            pkg.post_commands = post_commands

    return pkg.installed_variants
