============
Front Matter
============

Information about the awaitlet project.

Project Homepage
================

awaitlet is hosted on GitHub at https://github.com/sqlalchemy/awaitlet under the SQLAlchemy organization.

Releases and project status are available on Pypi at https://pypi.python.org/pypi/awaitlet.

The most recent published version of this documentation should be at https://awaitlet.sqlalchemy.org.


.. _installation:

Installation
============

Awaitlet is available on pypi under the name ``awaitlet``::

    $ pip install awaitlet


Dependencies
------------

awaitlet's sole dependency is the `greenlet <https://pypi.org/project/greenlet/>`_
library.  This is a widely used library that allows for coroutines in Python.

Greenlet is written in C.  While the package has binary releases available for
many platforms available, there may not be binary releases pre-built for some
architectures in some cases, in which case the environment will need Python
native extension build tools and dependencies to be present.     Greenlet also
may not be functional on pre-release cPython interpreters, as it
typically requires updates to be compatible with newer cPython releases.


Community
=========

awaitlet is developed by `Mike Bayer <http://techspot.zzzeek.org>`_, and is
part of the SQLAlchemy_ project.

User issues, discussion of potential bugs and features are most easily
discussed using `GitHub Discussions <https://github.com/sqlalchemy/awaitlet/discussions/>`_.

.. _bugs:

Bugs
====

Bugs and feature enhancements to awaitlet should be reported on the `GitHub
issue tracker
<https://github.com/sqlalchemy/awaitlet/issues/>`_.

.. _SQLAlchemy: https://www.sqlalchemy.org
