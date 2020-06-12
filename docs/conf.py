import sys
import os

# to allow autodoc to discover the documented modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

project = 'Votelib'
copyright = '2020, Jan Šimbera'
author = 'Jan Šimbera'

extensions = [
    'sphinx.ext.autodoc',
    'recommonmark',
    'nbsphinx',
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

templates_path = ['_templates']

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinxdoc'

html_static_path = ['_static']