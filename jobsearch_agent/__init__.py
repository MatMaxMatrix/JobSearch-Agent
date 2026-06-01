"""JobSearch-Agent: a toolkit for job search, CV generation, and application tracking.

The package provides tools to:

- Search for job postings online (LinkedIn, Indeed, Glassdoor via Google Search)
- Process and store job listing information
- Generate customized CVs tailored to job requirements
- Create targeted cover letters
- Organize application materials by job

Top-level imports are intentionally minimal so that ``import jobsearch_agent``
does not eagerly load heavy LLM dependencies. Import what you need from the
relevant subpackage:

>>> from jobsearch_agent.agents import call_cv_agent
>>> from jobsearch_agent.api.app import app
>>> from jobsearch_agent.utils import load_config

Entry points (installed via ``pip install .``):

- ``jobsearch-agent``: CLI (see :mod:`jobsearch_agent.cli`)
- ``jobsearch-api``: FastAPI server launcher (see :mod:`jobsearch_agent.api.server`)
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
