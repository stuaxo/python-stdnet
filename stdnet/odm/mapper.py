import copy
from inspect import ismodule

from stdnet.utils import native_str
from stdnet.utils.async import multi_async
from stdnet.utils.importer import import_module
from stdnet import getdb, InvalidTransaction

from .base import StdNetType, AlreadyRegistered
from .session import Manager, Session, ModelDictionary

__all__ = ['Router', 'model_iterator', 'all_models_sessions']
        
        
class Router(object):
    '''A router is a mapping of :class:`Model` to the registered
:class:`Manager` of that model::
    
    from stdnet import odm
    
    models = odm.Router()
    models.register(MyModel, ...)
    
    # dictionary Notation
    query = models[MyModel].query()
    
    # or dotted notation (lowercase)
    query = models.mymodel.query()
    
The ``models`` instance in the above snipped can be set globally if
one wishes to do so.
'''
    def __init__(self, default_backend=None, install_global=False):
        self._registered_models = ModelDictionary()
        self._registered_names = {}
        self._default_backend = default_backend
        self._install_global = install_global
        
    @property
    def default_backend(self):
        '''The default backend for this :class:`Router`. This is used when
calling the :meth:`register` method without explicitly passing a backend.'''
        return self._default_backend
    
    @property
    def registered_models(self):
        '''List of registered :class:`Model`.'''
        return list(self._registered_models)
    
    def __repr__(self):
        return '%s %s' % (self.__class__.__name.__, self._registered_models)
    
    def __str__(self):
        return str(self._registered_models)
    
    def __contains__(self, model):
        return model in self._registered_models
    
    def __getitem__(self, model):
        return self._registered_models[model]
    
    def __getattr__(self, name):
        if name in self._registered_names:
            return self._registered_names[name]
        else:
            return super(Router, self).__getattr__(name)
    
    def register(self, model, backend=None, include_related=True, **params):
        '''Register a :class:`Model` with this :class:`Router`. If the
model was already registered it does nothing.

:param model: a :class:`Model` class.
:param backend: a :class:`stdnet.BackendDataServer` or a
    :ref:`connection string <connection-string>`.
:param include_related: ``True`` if related models to ``model`` needs to be
    registered. Default ``True``.
:param params: Additional parameters for the :func:`getdb` function.
:return: the number of models registered.
'''
        backend = backend or self._default_backend
        backend = getdb(backend=backend, **params)
        registered = 0
        for model in models_from_model(model, include_related=include_related):
            if model in self._registered_models:
                continue
            registered += 1
            manager_class = getattr(model, 'manager_class', Manager)
            manager = manager_class(model, backend, self)
            self._registered_models[model] = manager
            attr_name = model._meta.name
            if attr_name not in self._registered_names:
                self._registered_names[attr_name] = manager
            if self._install_global:
                model.objects = manager
        if registered:
            return backend
        
    def flush(self, exclude=None):
        '''Flush all :attr:`registered_models` excluding the ones
in ``exclude`` (if provided).'''
        exclude = exclude or []
        results = []
        for manager in self._registered_models.values():
            if not manager.model._meta.name in exclude:
                results.append(manager.flush())
        return multi_async(results)
        
    def unregister(model=None):
        '''Unregister a ``model`` if provided, otherwise it unregister all
registered models. Return a list of unregistered model managers.'''
        if model is not None:
            try:
                manager = self._registered_models.pop(model)
            except KeyError:
                return
            if self._registered_names.get(manager._meta.name) == manager:
                self._registered_names.pop(manager._meta.name)
            return [manager]
        else:
            managers = list(self._registered_models.values())
            self._registered_models.clear()
            return managers
    
    def register_applications(self, applications, models=None, backends=None):
        '''A higher level registration functions for group of models located
on application modules.
It uses the :func:`model_iterator` function to iterate
through all :class:`Model` models available in ``applications``
and register them using the :func:`register` low level method.

:parameter applications: A String or a list of strings representing
    python dotted paths where models are implemented.
:parameter models: Optional list of models to include. If not provided
    all models found in *applications* will be included.
:parameter backends: optional dictionary which map a model or an
    application to a backend :ref:`connection string <connection-string>`.
:rtype: A list of registered :class:`Model`.

For example::

    
    mapper.register_application_models('mylib.myapp')
    mapper.register_application_models(['mylib.myapp', 'another.path'])
    mapper.register_application_models(pythonmodule)
    mapper.register_application_models(['mylib.myapp',pythonmodule])

'''
        return list(self._register_applications(applications, models, backends))
    
    def session(self, *models):
        '''Obatain a :class:`Session` for ``models``, if given, otherwise a
session for all :attr:`registered_models``, provided they have the same backend.
If the models don't share the same backend an :class:`InvalidTransaction`
error is raised.'''
        models = models or self._registered_models
        session = None
        for model in models:
            if model in self:
                if session is None:
                    session = self[model].session()
                else:
                    if session.backend != self[model].backend:
                        raise InvalidTransaction("Models are registered with "\
                                                 "different databases. Cannot "\
                                                 "create transaction.")
        return session
        
    def add(self, instance):
        '''Add an ``instance`` to its backend database. This is a shurtcut
method for::

    self.session().add(instance)
'''
        return self.session().add(instance)
    
    # PRIVATE METHODS
    
    def _register_applications(self, applications, models, backends):
        app_defaults = app_defaults or {}
        for model in model_iterator(applications):
            meta = model._meta
            name = str(model._meta)
            if models and name not in models:
                continue
            if name not in app_defaults:
                name = model._meta.app_label
            kwargs = app_defaults.get(name, default)
            if not isinstance(kwargs, dict):
                kwargs = {'backend': kwargs}
            else:
                kwargs = kwargs.copy()
            if self.register(model, include_related=False, **kwargs):
                yield model


def models_from_model(model, include_related=False, exclude=None):
    '''Generator of all model in model.'''
    exclude = exclude or set()
    if model and model not in exclude:
        exclude.add(model)
        if not model._meta.abstract:
            yield model
            if include_related:
                exclude = set(exclude or ())
                exclude.add(model)
                for field in model._meta.fields:
                    if hasattr(field, 'relmodel'):
                        for m in (field.relmodel, field.model):
                            for m in models_from_model(
                                            field.relmodel,
                                            include_related=include_related,
                                            exclude=exclude):
                                yield m
                for manytomany in model._meta.manytomany:
                    related = getattr(model, manytomany)
                    for m in models_from_model(related.model,
                                               include_related=include_related,
                                               exclude=exclude):
                        yield m

                        
def model_iterator(application, include_related=True):
    '''A generator of :class:`StdModel` classes found in *application*.

:parameter application: A python dotted path or an iterable over python
    dotted-paths where models are defined.

Only models defined in these paths are considered.

For example::

    from stdnet.odm import model_iterator

    APPS = ('stdnet.contrib.searchengine',
            'stdnet.contrib.timeseries')

    for model in model_iterator(APPS):
        ...

'''
    application = native_str(application)
    if ismodule(application) or isinstance(application, str):
        if ismodule(application):
            mod, application = application, application.__name__
        else:
            try:
                mod = import_module(application)
            except ImportError:
                # the module is not there
                mod = None
        if mod:
            label = application.split('.')[-1]
            try:
                mod_models = import_module('.models', application)
            except ImportError:
                mod_models = mod
            mod_name = mod.__name__
            label = getattr(mod_models, 'app_label', label)
            models = set()
            for name in dir(mod_models):
                value = getattr(mod_models, name)
                meta = getattr(value, '_meta', None)
                if isinstance(value, StdNetType) and meta:
                    for model in models_from_model(value, label=label,
                                            include_related=include_related):
                        if model not in models:
                            models.add(model)
                            yield model
    else:
        for app in application:
            for m in model_iterator(app):
                yield m


def all_models_sessions(models, processed=None, session=None):
    '''Given an iterable over models, return a generator of the same models
plus hidden models such as the through model of :class:`ManyToManyField`
through models.'''
    processed = processed if processed is not None else set()
    for model in models:
        if model and model not in processed:
            try:
                model_session = model.objects.session()
            except ModelNotRegistered:
                model_session = session
            yield model, model_session
            processed.add(model)
            for field in model._meta.fields:
                if hasattr(field, 'relmodel'):
                    for m in all_models_sessions((field.relmodel,), processed):
                        yield m
                if hasattr(field, 'through'):
                    for m in all_models_sessions((field.through,), processed,
                                                 model_session):
                        yield m

