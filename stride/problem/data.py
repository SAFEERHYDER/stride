
import gc
import copy
import numpy as np
import scipy.ndimage

import mosaic

from .base import GriddedSaved
from ..core import Variable
from .. import plotting


__all__ = ['Data', 'StructuredData', 'ScalarField', 'VectorField', 'Traces']


@mosaic.tessera
class Data(GriddedSaved, Variable):
    """
    Objects of this type represent Data defined over a grid and on which mathematical
    operations might be performed. This data might or might not be structured.

    """

    def __init__(self, **kwargs):
        GriddedSaved.__init__(self, **kwargs)
        Variable.__init__(self, **kwargs)

    def clear_grad(self):
        raise NotImplementedError('Unimplemented Data method clear_grad')

    def process_grad(self):
        raise NotImplementedError('Unimplemented Data method process_grad')

    def __add__(self, other):
        raise NotImplementedError('Operator + has not been implemented for class %s' % self.__class__.__name__)

    def __sub__(self, other):
        raise NotImplementedError('Operator - has not been implemented for class %s' % self.__class__.__name__)

    def __mul__(self, other):
        raise NotImplementedError('Operator * has not been implemented for class %s' % self.__class__.__name__)

    def __pow__(self, power, modulo=None):
        raise NotImplementedError('Operator ** has not been implemented for class %s' % self.__class__.__name__)

    def __truediv__(self, other):
        raise NotImplementedError('Operator / has not been implemented for class %s' % self.__class__.__name__)

    def __floordiv__(self, other):
        raise NotImplementedError('Operator // has not been implemented for class %s' % self.__class__.__name__)

    def __iadd__(self, other):
        raise NotImplementedError('Operator + has not been implemented for class %s' % self.__class__.__name__)

    def __isub__(self, other):
        raise NotImplementedError('Operator - has not been implemented for class %s' % self.__class__.__name__)

    def __imul__(self, other):
        raise NotImplementedError('Operator * has not been implemented for class %s' % self.__class__.__name__)

    def __ipow__(self, power, modulo=None):
        raise NotImplementedError('Operator ** has not been implemented for class %s' % self.__class__.__name__)

    def __itruediv__(self, other):
        raise NotImplementedError('Operator / has not been implemented for class %s' % self.__class__.__name__)

    def __ifloordiv__(self, other):
        raise NotImplementedError('Operator // has not been implemented for class %s' % self.__class__.__name__)

    __radd__ = __add__
    __rsub__ = __sub__
    __rmul__ = __mul__
    __rtruediv__ = __truediv__
    __rfloordiv__ = __floordiv__


@mosaic.tessera
class StructuredData(Data):
    """
    Objects of this type represent data defined over a structured grid.

    This grid is on which the data lives is fully defined by the ``shape`` parameter. Optionally,
    an ``extended_shape`` may be provided if the data is defined over an inner and extended domain.
    If an extended domain is defined, the ``inner`` parameter can be used to determine the position
    of the inner domain within the larger extended domain.

    Parameters
    ----------
    name : str
        Name of the data.
    shape : tuple
        Shape of the inner domain of the data.
    extended_shape : tuple, optional
        Shape of the extended domain of the data, defaults to the ``shape``.
    inner : tuple, optional
        Tuple of slices defining the location of the inner domain inside the
        extended domain, defaults to the inner domain being centred.
    dtype : data-type, optional
        Data type of the data, defaults to float32.
    data : ndarray, optional
        Data with which to initialise the internal buffer, defaults to a new array. By default,
        no copies of the buffer are made if provided.
    grid : Grid or any of Space or Time
        Grid on which the Problem is defined

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        shape = kwargs.pop('shape', None)
        extended_shape = kwargs.pop('extended_shape', None)
        inner = kwargs.pop('inner', None)
        dtype = kwargs.pop('dtype', np.float32)

        if shape is not None:
            extended_shape = extended_shape or shape

            if inner is None:
                extra = [each_extended - each_shape
                         for each_extended, each_shape in zip(extended_shape, shape)]
                inner = tuple([slice(each_extra, each_extra + each_shape)
                               for each_extra, each_shape in zip(extra, shape)])

        self._shape = shape
        self._extended_shape = extended_shape
        self._inner = inner
        self._dtype = dtype

        self._data = None
        data = kwargs.pop('data', None)

        if data is not None:
            self._data = self.pad_data(data)

        self.grad = None
        self.prec = None

    def alike(self, *args, **kwargs):
        """
        Create a data object that shares its characteristics with this object.

        The same parameters as those given to ``__init__`` are valid here. Otherwise the
        new object will be configured to be like this one.

        Returns
        -------
        StructuredData
            Newly created StructuredData.

        """
        kwargs['shape'] = kwargs.pop('shape', self.shape)
        kwargs['extended_shape'] = kwargs.pop('extended_shape', self.extended_shape)
        kwargs['inner'] = kwargs.pop('inner', self.inner)
        kwargs['dtype'] = kwargs.pop('dtype', self.dtype)
        kwargs['grid'] = kwargs.pop('grid', self.grid)

        return self.__class__(*args, **kwargs)

    def copy(self):
        """
        Create a deep copy of the data object.

        Returns
        -------
        StructuredData
            Newly created StructuredData.

        """
        return copy.deepcopy(self)

    @property
    def data(self):
        """
        Data values inside the inner domain, as an ndarray.

        """
        if self._data is None:
            self.allocate()

        return self._data[self._inner]

    @property
    def extended_data(self):
        """
        Data values inside the extended domain, as an ndarray.

        """
        if self._data is None:
            self.allocate()

        return self._data

    @property
    def shape(self):
        """
        Shape of the inner domain, as a tuple.

        """
        return self._shape

    @property
    def extended_shape(self):
        """
        Shape of the extended domain, as a tuple.

        """
        return self._extended_shape

    @property
    def inner(self):
        """
        Slices that determine the location of the inner domain with respect to the extended domain,
        as a tuple of slices.

        """
        return self._inner

    @property
    def allocated(self):
        """
        Whether or not the data has been allocated.

        """
        return self._data is not None

    @property
    def dtype(self):
        """
        Data-type of the data.

        """
        return self._dtype

    def clear_grad(self):
        """
        Initialise and clear the internal buffers for the gradient and preconditioner.

        Returns
        -------

        """
        if not self.needs_grad:
            return

        if self.grad is None:
            self.grad = self.alike(name='%s_grad' % self.name)
            self.grad.prec = self.alike(name='%s_prec' % self.name)

        self.grad.fill(0.)
        self.grad.prec.fill(0.)

    def process_grad(self, prec_scale=1e-6):
        """
        Process the gradient by applying the pre-conditioner to it.

        Parameters
        ----------
        prec_scale : float, optional
            Condition scaling for the preconditioner.

        Returns
        -------

        """
        if not self.needs_grad:
            return

        grad = self.grad
        prec = grad.prec

        prec += prec_scale * np.max(prec.data) + 1e-31
        grad /= prec

        self.grad = None

        return grad

    def allocate(self):
        """
        Allocate the data if this has not been allocated yet.

        Returns
        -------

        """
        if self._data is None:
            self._data = np.empty(self._extended_shape, dtype=self._dtype)

    def deallocate(self):
        """
        Deallocate the data.

        Returns
        -------

        """
        if self._data is not None:
            del self._data
            self._data = None
            gc.collect()

    def fill(self, value):
        """
        Fill the data with a certain value

        Parameters
        ----------
        value : float
            Value with which to fill the data.

        Returns
        -------

        """
        if self._data is None:
            self.allocate()

        self._data.fill(value)

    def pad_data(self, data, smooth=False):
        """
        Pad input data to match the extended shape of the StructuredData.

        Parameters
        ----------
        data : ndarray
            Array to pad.
        smooth : bool, optional
            Whether or not to smooth the padding area, defaults to False

        Returns
        -------
        ndarray
            Padded array.

        """
        shape = data.shape
        pad_widths = [each_extended - each_shape for each_extended, each_shape in
                      zip(self._extended_shape, shape)]
        pad_widths = [[each // 2, each // 2] for each in pad_widths]

        if np.asarray(pad_widths).sum() > 0:
            data = np.pad(data, pad_widths, mode='edge')

            if smooth is True:
                for dim, width in zip(range(len(pad_widths)), pad_widths):
                    # : slices
                    all_ind = [slice(0, d) for d in data.shape]

                    for pos in range(0, width[0], 5):
                        sigma = pos / width[0] * 3.0

                        # Left slice for dimension
                        all_ind[dim] = slice(0, width[0] + 1 - pos)
                        data[tuple(all_ind)] = scipy.ndimage.gaussian_filter(data[tuple(all_ind)], sigma=sigma)

                        # right slice for dimension
                        all_ind[dim] = slice(data.shape[dim] - width[1] - 1 + pos, data.shape[dim])
                        data[tuple(all_ind)] = scipy.ndimage.gaussian_filter(data[tuple(all_ind)], sigma=sigma)

            return data

        else:
            return data

    def _prepare_op(self, other):
        res = self.copy()
        other_data = self._prepare_other(other)

        return res, other_data

    def _prepare_other(self, other):
        other_data = other
        if isinstance(other, StructuredData):
            if not isinstance(self, StructuredData):
                raise ValueError('Data of type %s and %s cannot be operated together' %
                                 (type(self), type(other)))

            other_data = other.extended_data

        return other_data

    @staticmethod
    def _op_grad(res, other, op):
        if not hasattr(other, 'grad'):
            return

        if res.grad is not None and other.grad is not None:
            res.grad = getattr(res.grad, op)(other.grad)

    @staticmethod
    def _op_prec(res, other, op):
        if not hasattr(other, 'prec'):
            return

        if res.prec is not None and other.prec is not None:
            res.prec = getattr(res.prec, op)(other.prec)

    def __add__(self, other):
        res, other_data = self._prepare_op(other)
        res.extended_data[:] = res.extended_data.__add__(other_data)

        self._op_grad(res, other, '__add__')
        self._op_prec(res, other, '__add__')

        return res

    def __sub__(self, other):
        res, other_data = self._prepare_op(other)
        res.extended_data[:] = res.extended_data.__sub__(other_data)

        self._op_grad(res, other, '__sub__')
        self._op_prec(res, other, '__sub__')

        return res

    def __mul__(self, other):
        res, other_data = self._prepare_op(other)
        res.extended_data[:] = res.extended_data.__mul__(other_data)

        self._op_grad(res, other, '__mul__')
        self._op_prec(res, other, '__mul__')

        return res

    def __pow__(self, power, modulo=None):
        res = self.copy()
        res.extended_data[:] = res.extended_data.__pow__(power)

        return res

    def __truediv__(self, other):
        res, other_data = self._prepare_op(other)
        res.extended_data[:] = res.extended_data.__truediv__(other_data)

        self._op_grad(res, other, '__truediv__')
        self._op_prec(res, other, '__truediv__')

        return res

    def __floordiv__(self, other):
        res, other_data = self._prepare_op(other)
        res.extended_data[:] = res.extended_data.__floordiv__(other_data)

        self._op_grad(res, other, '__floordiv__')
        self._op_prec(res, other, '__floordiv__')

        return res

    def __iadd__(self, other):
        res = self
        other_data = self._prepare_other(other)
        res.extended_data.__iadd__(other_data)

        self._op_grad(res, other, '__iadd__')
        self._op_prec(res, other, '__iadd__')

        return res

    def __isub__(self, other):
        res = self
        other_data = self._prepare_other(other)
        res.extended_data.__isub__(other_data)

        self._op_grad(res, other, '__isub__')
        self._op_prec(res, other, '__isub__')

        return res

    def __imul__(self, other):
        res = self
        other_data = self._prepare_other(other)
        res.extended_data.__imul__(other_data)

        self._op_grad(res, other, '__imul__')
        self._op_prec(res, other, '__imul__')

        return res

    def __ipow__(self, power, modulo=None):
        res = self
        res.extended_data.__ipow__(power)

        return res

    def __itruediv__(self, other):
        res = self
        other_data = self._prepare_other(other)
        res.extended_data.__itruediv__(other_data)

        self._op_grad(res, other, '__itruediv__')
        self._op_prec(res, other, '__itruediv__')

        return res

    def __ifloordiv__(self, other):
        res = self
        other_data = self._prepare_other(other)
        res.extended_data.__ifloordiv__(other_data)

        self._op_grad(res, other, '__ifloordiv__')
        self._op_prec(res, other, '__ifloordiv__')

        return res

    __radd__ = __add__
    __rsub__ = __sub__
    __rmul__ = __mul__
    __rtruediv__ = __truediv__
    __rfloordiv__ = __floordiv__

    def __get_desc__(self):
        if self._data is None:
            self.allocate()

        inner = []
        for each in self._inner:
            inner.append([
                str(each.start),
                str(each.stop),
                str(each.step),
            ])

        description = {
            'shape': self._shape,
            'extended_shape': self._extended_shape,
            'inner': inner,
            'dtype': str(np.dtype(self._dtype)),
            'data': self.data,
        }

        return description

    def __set_desc__(self, description):
        self._shape = description.shape
        self._extended_shape = description.extended_shape
        self._dtype = np.dtype(description.dtype)

        inner = []
        for each in description.inner:
            inner.append(slice(
                int(each[0]) if each[0] != 'None' else None,
                int(each[1]) if each[1] != 'None' else None,
                int(each[2]) if each[2] != 'None' else None,
            ))

        self._inner = tuple(inner)

        data = description.data
        if hasattr(data, 'load'):
            data = data.load()

        self.extended_data[:] = self.pad_data(data)


@mosaic.tessera
class ScalarField(StructuredData):
    """
    Objects of this type describe a scalar field defined over the spatial grid. Scalar fields
    can also be time-dependent.

    By default, the domain over which the field is defined is determined by the grid
    provided. This can be overwritten by providing a defined ``shape`` instead.

    Parameters
    ----------
    name : str
        Name of the data.
    time_dependent : bool, optional
        Whether or not the field is time-dependent, defaults to False.
    shape : tuple, optional
        Shape of the inner domain of the data.
    extended_shape : tuple, optional
        Shape of the extended domain of the data, defaults to the ``shape``.
    inner : tuple, optional
        Tuple of slices defining the location of the inner domain inside the
        extended domain, defaults to the inner domain being centred.
    dtype : data-type, optional
        Data type of the data, defaults to float32.
    grid : Grid or any of Space or Time
        Grid on which the Problem is defined

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        time_dependent = kwargs.pop('time_dependent', False)
        self._time_dependent = time_dependent

        if self.space is not None and self._shape is None:
            shape = ()
            extended_shape = ()
            inner = ()
            if self._time_dependent:
                shape += (self.time.num,)
                extended_shape += (self.time.extended_num,)
                inner += (self.time.inner,)

            shape += self.space.shape
            extended_shape += self.space.extended_shape
            inner += self.space.inner

            self._shape = shape
            self._extended_shape = extended_shape
            self._inner = inner

    def alike(self, *args, **kwargs):
        """
        Create a data object that shares its characteristics with this object.

        The same parameters as those given to ``__init__`` are valid here. Otherwise the
        new object will be configured to be like this one.

        Returns
        -------
        ScalarField
            Newly created ScalarField.

        """
        kwargs['time_dependent'] = kwargs.pop('time_dependent', self.time_dependent)

        return super().alike(*args, **kwargs)

    @property
    def time_dependent(self):
        """
        Whether or not the field is time dependent.

        """
        return self._time_dependent

    def plot(self, **kwargs):
        """
        Plot the inner domain of the field.

        Parameters
        ----------
        kwargs
            Arguments for plotting.

        Returns
        -------
        axes
            Axes on which the plotting is done.

        """
        title = kwargs.pop('title', self.name)
        plot = kwargs.pop('plot', True)

        axis = plotting.plot_scalar_field(self.data, title=title,
                                          origin=self.space.origin, limit=self.space.limit,
                                          **kwargs)

        if plot is True:
            plotting.show(axis)

        return axis

    def extended_plot(self, **kwargs):
        """
        Plot the extended domain of the field.

        Parameters
        ----------
        kwargs
            Arguments for plotting.

        Returns
        -------
        axes
            Axes on which the plotting is done.

        """
        title = kwargs.pop('title', self.name)
        plot = kwargs.pop('plot', True)

        axis = plotting.plot_scalar_field(self.extended_data, title=title,
                                          origin=self.space.pml_origin, limit=self.space.extended_limit,
                                          **kwargs)

        if plot is True:
            plotting.show(axis)

        return axis

    def __get_desc__(self):
        description = super().__get_desc__()
        description['time_dependent'] = self._time_dependent

        return description

    def __set_desc__(self, description):
        # TODO Not entirely convinved by this solution
        # super().__set_desc__(description)

        # TODO and this should not be repeated
        if self.space is not None and self._shape is None:
            shape = ()
            extended_shape = ()
            inner = ()
            if self._time_dependent:
                shape += (self.time.num,)
                extended_shape += (self.time.extended_num,)
                inner += (self.time.inner,)

            shape += self.space.shape
            extended_shape += self.space.extended_shape
            inner += self.space.inner

            self._shape = shape
            self._extended_shape = extended_shape
            self._inner = inner

        self._dtype = np.dtype(description.dtype)
        self._time_dependent = description.time_dependent

        data = description.data
        if hasattr(data, 'load'):
            data = data.load()

        self.extended_data[:] = self.pad_data(data)


@mosaic.tessera
class VectorField(ScalarField):
    """
    Objects of this type describe a vector field defined over the spatial grid. Vector fields
    can also be time-dependent.

    By default, the domain over which the field is defined is determined by the grid
    provided. This can be overwritten by providing a defined ``shape`` instead.

    Parameters
    ----------
    name : str
        Name of the data.
    dim : int, optional
        Number of dimensions for the vector field, defaults to the spatial dimensions.
    time_dependent : bool, optional
        Whether or not the field is time-dependent, defaults to False.
    shape : tuple, optional
        Shape of the inner domain of the data.
    extended_shape : tuple, optional
        Shape of the extended domain of the data, defaults to the ``shape``.
    inner : tuple, optional
        Tuple of slices defining the location of the inner domain inside the
        extended domain, defaults to the inner domain being centred.
    dtype : data-type, optional
        Data type of the data, defaults to float32.
    grid : Grid or any of Space or Time
        Grid on which the Problem is defined

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        dim = kwargs.pop('dim', False)
        self._dim = dim

        if self.space is not None and self._shape is not None:
            self._dim = dim or self.space.dim
            self._shape = (self._dim,) + self._shape
            self._extended_shape = (self._dim,) + self._extended_shape
            self._inner = (slice(0, None),) + self._inner

    def alike(self, *args, **kwargs):
        """
        Create a data object that shares its characteristics with this object.

        The same parameters as those given to ``__init__`` are valid here. Otherwise the
        new object will be configured to be like this one.

        Returns
        -------
        VectorField
            Newly created VectorField.

        """
        kwargs['dim'] = kwargs.pop('dim', self.dim)

        return super().alike(*args, **kwargs)

    @property
    def dim(self):
        """
        Number of dimensions of the vector field.

        """
        return self._dim

    def __get_desc__(self):
        description = super().__get_desc__()
        description['dim'] = self._dim

        return description

    def __set_desc__(self, description):
        super().__set_desc__(description)

        self._dim = description.dim


@mosaic.tessera
class Traces(StructuredData):
    """
    Objects of this type describe a set of time traces defined over the time grid.

    By default, the domain over which the field is defined is determined by the time grid
    provided. This can be overwritten by providing a defined ``shape`` instead.

    Parameters
    ----------
    name : str
        Name of the data.
    transducer_ids : list
        List of IDs to which the time traces correspond.
    shape : tuple, optional
        Shape of the inner domain of the data.
    extended_shape : tuple, optional
        Shape of the extended domain of the data, defaults to the ``shape``.
    inner : tuple, optional
        Tuple of slices defining the location of the inner domain inside the
        extended domain, defaults to the inner domain being centred.
    dtype : data-type, optional
        Data type of the data, defaults to float32.
    grid : Grid or any of Space or Time
        Grid on which the Problem is defined

    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        transducer_ids = kwargs.pop('transducer_ids', None)
        self._transducer_ids = transducer_ids

        if self._transducer_ids is not None and self._shape is None:
            shape = (len(self._transducer_ids), self.time.num)
            extended_shape = (len(self._transducer_ids), self.time.extended_num)
            inner = (slice(0, None), self.time.inner)

            self._shape = shape
            self._extended_shape = extended_shape
            self._inner = inner

    def alike(self, *args, **kwargs):
        """
        Create a data object that shares its characteristics with this object.

        The same parameters as those given to ``__init__`` are valid here. Otherwise the
        new object will be configured to be like this one.

        Returns
        -------
        Traces
            Newly created Traces.

        """
        kwargs['transducer_ids'] = kwargs.pop('transducer_ids', self.transducer_ids)

        return super().alike(*args, **kwargs)

    @property
    def transducer_ids(self):
        """
        List of transducer IDs associated with the traces.

        """
        return self._transducer_ids

    @property
    def num_transducers(self):
        """
        Number of transducers.

        """
        return len(self._transducer_ids)

    def get(self, id):
        """
        Get one trace based on a transducer ID, selecting the inner domain.

        Parameters
        ----------
        id : int
            Transducer ID.

        Returns
        -------
        1d-array
            Time trace.

        """
        if self._data is None:
            self.allocate()

        index = list(self._transducer_ids).index(id)
        return self.data[index, :]

    def get_extended(self, id):
        """
        Get one trace based on a transducer ID, selecting the extended domain.

        Parameters
        ----------
        id : int
            Transducer ID.

        Returns
        -------
        1d-array
            Time trace.

        """
        if self._data is None:
            self.allocate()

        index = list(self._transducer_ids).index(id)
        return self.extended_data[index, :]

    def plot(self, **kwargs):
        """
        Plot the inner domain of the traces as a shot gather.

        Parameters
        ----------
        kwargs
            Arguments for plotting.

        Returns
        -------
        axes
            Axes on which the plotting is done.

        """
        title = kwargs.pop('title', self.name)
        plot = kwargs.pop('plot', True)
        time_axis = self.time.grid / 1e-6

        axis = plotting.plot_gather(self.transducer_ids, time_axis, self.data,
                                    title=title, **kwargs)

        if plot is True:
            plotting.show(axis)

        return axis

    def plot_one(self, id, **kwargs):
        """
        Plot the the inner domain of one of the traces.

        Parameters
        ----------
        id : int
            Transducer ID.
        kwargs
            Arguments for plotting.

        Returns
        -------
        axes
            Axes on which the plotting is done.

        """
        title = kwargs.pop('title', self.name)
        plot = kwargs.pop('plot', True)
        trace = self.get(id)
        time_axis = self.time.grid / 1e-6

        axis = plotting.plot_trace(time_axis, trace,
                                   title=title, **kwargs)

        if plot is True:
            plotting.show(axis)

        return axis

    def __get_desc__(self):
        description = super().__get_desc__()
        description['num_transducers'] = self.num_transducers
        description['transducer_ids'] = self._transducer_ids

        return description

    def __set_desc__(self, description):
        super().__set_desc__(description)

        self._transducer_ids = description.transducer_ids