"""Custom Bazel rule for building AWS Lambda deployment zips.

Each Lambda gets a zip containing only its transitive Python dependencies
(with the ``src/`` prefix stripped) and optionally SQL template files remapped
under ``doubleday/sql/``.
"""

load("@rules_python//python:defs.bzl", "PyInfo")

def _lambda_zip_impl(ctx):
    """Collect transitive sources, write a manifest, invoke the zipper."""
    zip_file = ctx.actions.declare_file(ctx.attr.name + ".zip")
    manifest = ctx.actions.declare_file(ctx.attr.name + "_manifest.txt")

    # Collect transitive Python sources from all deps.
    py_depsets = [
        dep[PyInfo].transitive_sources
        for dep in ctx.attr.deps
        if PyInfo in dep
    ]
    py_files = depset(transitive = py_depsets)

    # Collect SQL data files.
    sql_depsets = [
        target[DefaultInfo].files
        for target in ctx.attr.sql_data
    ]
    sql_files = depset(transitive = sql_depsets)

    all_inputs = depset(transitive = [py_files, sql_files])

    strip = ctx.attr.strip_prefix
    sql_prefix = ctx.attr.sql_zip_prefix

    # Force Bazel to write file paths to param files (one per group).
    # Without use_param_file, add_all expands into individual positional args.
    py_args = ctx.actions.args()
    py_args.use_param_file("%s", use_always = True)
    py_args.set_param_file_format("multiline")
    py_args.add_all(py_files)

    sql_args = ctx.actions.args()
    sql_args.use_param_file("%s", use_always = True)
    sql_args.set_param_file_format("multiline")
    sql_args.add_all(sql_files)

    ctx.actions.run_shell(
        inputs = all_inputs,
        outputs = [zip_file, manifest],
        tools = [ctx.executable._zipper],
        arguments = [py_args, sql_args],
        command = """\
set -euo pipefail

ZIP_OUT="{zip_out}"
MANIFEST="{manifest}"
STRIP="{strip}"
SQL_PREFIX="{sql_prefix}"
ZIPPER="{zipper}"
PY_PARAMS="$1"
SQL_PARAMS="$2"

> "$MANIFEST"

# Process Python files from param file.
if [ -s "$PY_PARAMS" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        zip_path="${{f#$STRIP/}}"
        printf '%s\\t%s\\n' "$f" "$zip_path" >> "$MANIFEST"
    done < "$PY_PARAMS"
fi

# Process SQL files from param file.
if [ -s "$SQL_PARAMS" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        relative="${{f#sql/}}"
        zip_path="${{SQL_PREFIX}}/${{relative}}"
        printf '%s\\t%s\\n' "$f" "$zip_path" >> "$MANIFEST"
    done < "$SQL_PARAMS"
fi

"$ZIPPER" "$ZIP_OUT" "$MANIFEST"
""".format(
            zip_out = zip_file.path,
            manifest = manifest.path,
            strip = strip,
            sql_prefix = sql_prefix,
            zipper = ctx.executable._zipper.path,
        ),
        mnemonic = "LambdaZip",
        progress_message = "Building Lambda zip %s" % ctx.label,
        use_default_shell_env = False,
    )

    return [DefaultInfo(files = depset([zip_file]))]

lambda_zip = rule(
    implementation = _lambda_zip_impl,
    attrs = {
        "deps": attr.label_list(
            providers = [PyInfo],
            doc = "py_library targets whose transitive sources are included in the zip.",
        ),
        "sql_data": attr.label_list(
            allow_files = [".sql"],
            default = [],
            doc = "Filegroup targets for SQL template files to include.",
        ),
        "strip_prefix": attr.string(
            default = "src",
            doc = "Path prefix to strip from Python source file paths in the zip.",
        ),
        "sql_zip_prefix": attr.string(
            default = "doubleday/sql",
            doc = "Prefix for SQL files inside the zip.",
        ),
        "_zipper": attr.label(
            default = "//bazel:create_lambda_zip",
            executable = True,
            cfg = "exec",
        ),
    },
    doc = "Builds an AWS Lambda deployment zip from py_library deps and optional SQL data files.",
)
