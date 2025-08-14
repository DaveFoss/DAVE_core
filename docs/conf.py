extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.ifconfig",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]
source_suffix = ".rst"
master_doc = "index"
project = "DAVE_core"
year = "2025"
author = "DAVE_core Developers"
copyright = f"{year}, {author}"
version = release = "v1.3.1"

pygments_style = "trac"
templates_path = ["."]
extlinks = {
    "issue": ("https://github.com/DaveFoss/DAVE_core/issues/%s", "#%s"),
    "pr": ("https://github.com/DaveFoss/DAVE_core/pull/%s", "PR #%s"),
}

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "github_url": "https://github.com/DaveFoss/DAVE_core/",
}

html_use_smartypants = True
html_last_updated_fmt = "%b %d, %Y"
html_split_index = False
html_short_title = f"{project}-{version}"

napoleon_use_ivar = True
napoleon_use_rtype = False
napoleon_use_param = False
