
import mosaic

from .pipeline import Pipeline


__all__ = ['ProcessWavelets', 'ProcessTraces',
           'ProcessGlobalGradient', 'ProcessModelIteration']

# TODO Default configuration of pipelines should be better defined


@mosaic.tessera
class ProcessWavelets(Pipeline):
    """
    Default pipeline to process wavelets before running the forward problem.

    **Default steps:**

    - ``filter_wavelets``

    """

    def __init__(self, steps=None, no_grad=False, **kwargs):
        steps = steps or []

        super().__init__(steps, no_grad=no_grad, **kwargs)


@mosaic.tessera
class ProcessTraces(Pipeline):
    """
    Default pipeline to process modelled and observed before running the functional.

    **Default steps:**

    - ``mute_traces``
    - ``filter_traces``
    - ``norm_per_shot``

    """

    def __init__(self, steps=None, no_grad=False, **kwargs):
        steps = steps or []

        if kwargs.pop('filter_offsets', False):
            steps.append(('filter_offsets', False))  # do not raise if not present

        if kwargs.pop('mute_traces', True):
            steps.append('mute_traces')

        steps.append('filter_traces')

        norm_per_shot = kwargs.pop('norm_per_shot', True)
        norm_per_trace = kwargs.pop('norm_per_trace', False)

        if norm_per_trace:
            steps.append('norm_per_trace')
        elif norm_per_shot:
            steps.append('norm_per_shot')

        super().__init__(steps, no_grad=no_grad, **kwargs)


@mosaic.tessera
class ProcessGlobalGradient(Pipeline):
    """
    Default pipeline to process the global gradient before updating the variable.

    **Default steps:**

    - ``mask``
    - ``smooth_field``
    - ``norm_field``

    """

    def __init__(self, steps=None, no_grad=True, **kwargs):
        steps = steps or []

        mask = kwargs.pop('mask', True)
        if mask:
            steps.append('mask')

        smooth = kwargs.pop('smooth', True)
        if smooth:
            steps.append('smooth_field')

        norm = kwargs.pop('norm', True)
        if norm:
            steps.append('norm_field')

        super().__init__(steps, no_grad=no_grad, **kwargs)


@mosaic.tessera
class ProcessModelIteration(Pipeline):
    """
    Default pipeline to process the model after each iteration.

    **Default steps:**

    - ``clip``

    """

    def __init__(self, steps=None, no_grad=True, **kwargs):
        steps = steps or []
        steps.append('clip')

        super().__init__(steps, no_grad=no_grad, **kwargs)
