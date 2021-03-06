manager - starting, stopping, signalling
========================================

.. currentmodule:: jupyter_client

.. autoclass:: KernelManager

   .. attribute:: kernel_name

      The name of the kernel to launch (see :ref:`kernelspecs`).

   .. autoattribute:: provisioner

      The kernel provisioner with which this :class:`KernelManager` is communicating.  This will generally be a :class:`LocalProvisioner` instance unless the kernelspec indicates otherwise.

   .. automethod:: start_kernel

   .. automethod:: is_alive

   .. automethod:: interrupt_kernel

   .. automethod:: signal_kernel

   .. automethod:: client

      For the client API, see :mod:`jupyter_client.client`.

   .. automethod:: blocking_client

   .. automethod:: shutdown_kernel

   .. automethod:: restart_kernel

multikernelmanager - controlling multiple kernels
-------------------------------------------------

.. autoclass:: MultiKernelManager

   This exposes the same methods as :class:`~jupyter_client.manager.KernelManager`,
   but their first parameter is a kernel ID, a string identifying the kernel
   instance. Typically these are UUIDs picked by :meth:`start_kernel`

   .. automethod:: start_kernel

   .. automethod:: list_kernel_ids

   .. automethod:: get_kernel

   .. automethod:: remove_kernel

   .. automethod:: shutdown_all

Utility functions
-----------------

.. autofunction:: run_kernel
