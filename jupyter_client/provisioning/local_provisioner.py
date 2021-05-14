"""Kernel Provisioner Classes"""
# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import asyncio
import os
import signal
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from ..launcher import launch_kernel
from ..localinterfaces import is_local_ip
from ..localinterfaces import local_ips
from .provisioner_base import KernelProvisionerBase


class LocalProvisioner(KernelProvisionerBase):

    process = None
    _exit_future = None
    pid = None
    pgid = None
    ip = None

    def has_process(self) -> bool:
        return self.process is not None

    async def poll(self) -> Optional[int]:
        ret = 0
        if self.process:
            ret = self.process.poll()
        return ret

    async def wait(self) -> Optional[int]:
        ret = 0
        if self.process:
            # Use busy loop at 100ms intervals, polling until the process is
            # not alive.  If we find the process is no longer alive, complete
            # its cleanup via the blocking wait().  Callers are responsible for
            # issuing calls to wait() using a timeout (see kill()).
            while await self.poll() is None:
                await asyncio.sleep(0.1)

            # Process is no longer alive, wait and clear
            ret = self.process.wait()
            self.process = None  # allow has_process to now return False
        return ret

    async def send_signal(self, signum: int) -> None:
        """Sends a signal to the process group of the kernel (this
        usually includes the kernel and any subprocesses spawned by
        the kernel).

        Note that since only SIGTERM is supported on Windows, we will
        check if the desired signal is for interrupt and apply the
        applicable code on Windows in that case.
        """
        if self.process:
            if signum == signal.SIGINT and sys.platform == 'win32':
                from ..win_interrupt import send_interrupt

                send_interrupt(self.process.win32_interrupt_event)
                return

            # Prefer process-group over process
            if self.pgid and hasattr(os, "killpg"):
                try:
                    os.killpg(self.pgid, signum)
                    return
                except OSError:
                    pass
            try:
                self.process.send_signal(signum)
            except OSError:
                pass
            return

    async def kill(self, restart: bool = False) -> None:
        if self.process:
            try:
                self.process.kill()
            except OSError as e:
                # In Windows, we will get an Access Denied error if the process
                # has already terminated. Ignore it.
                if sys.platform == 'win32':
                    if e.winerror != 5:
                        raise
                # On Unix, we may get an ESRCH error if the process has already
                # terminated. Ignore it.
                else:
                    from errno import ESRCH

                    if e.errno != ESRCH:
                        raise

    async def terminate(self, restart: bool = False) -> None:
        if self.process:
            return self.process.terminate()

    async def cleanup(self, restart: bool = False) -> None:
        pass

    async def pre_launch(self, **kwargs: Any) -> Dict[str, Any]:
        """Perform any steps in preparation for kernel process launch.

        This includes applying additional substitutions to the kernel launch command and env.
        It also includes preparation of launch parameters.

        Returns the updated kwargs.
        """

        # If we have a kernel_manager pop it out of the args and use it to retain b/c.
        # This should be considered temporary until a better division of labor can be defined.
        km = kwargs.pop('kernel_manager', None)
        if km:
            if km.transport == 'tcp' and not is_local_ip(km.ip):
                raise RuntimeError(
                    "Can only launch a kernel on a local interface. "
                    "This one is not: %s."
                    "Make sure that the '*_address' attributes are "
                    "configured properly. "
                    "Currently valid addresses are: %s" % (km.ip, local_ips())
                )
            # build the Popen cmd
            extra_arguments = kwargs.pop('extra_arguments', [])

            # write connection file / get default ports
            km.write_connection_file()  # TODO - change when handshake pattern is adopted
            self._connection_info = km.get_connection_info()

            kernel_cmd = km.format_kernel_cmd(
                extra_arguments=extra_arguments
            )  # This needs to remain here for b/c
        else:
            extra_arguments = kwargs.pop('extra_arguments', [])
            kernel_cmd = self.kernel_spec.argv + extra_arguments

        return await super().pre_launch(cmd=kernel_cmd, **kwargs)

    async def launch_kernel(self, cmd: List[str], **kwargs: Any) -> None:
        scrubbed_kwargs = LocalProvisioner._scrub_kwargs(kwargs)
        self.process = launch_kernel(cmd, **scrubbed_kwargs)
        pgid = None
        if hasattr(os, "getpgid"):
            try:
                pgid = os.getpgid(self.process.pid)  # type: ignore
            except OSError:
                pass

        self.pid = self.process.pid
        self.pgid = pgid

    @staticmethod
    def _scrub_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Remove any keyword arguments that Popen does not tolerate."""
        keywords_to_scrub: List[str] = ['extra_arguments', 'kernel_id', 'kernel_manager']
        scrubbed_kwargs = kwargs.copy()
        for kw in keywords_to_scrub:
            scrubbed_kwargs.pop(kw, None)
        return scrubbed_kwargs

    async def get_provisioner_info(self) -> Dict:
        """Captures the base information necessary for persistence relative to this instance."""
        provisioner_info = await super().get_provisioner_info()
        provisioner_info.update({'pid': self.pid, 'pgid': self.pgid, 'ip': self.ip})
        return provisioner_info

    async def load_provisioner_info(self, provisioner_info: Dict) -> None:
        """Loads the base information necessary for persistence relative to this instance."""
        await super().load_provisioner_info(provisioner_info)
        self.pid = provisioner_info['pid']
        self.pgid = provisioner_info['pgid']
        self.ip = provisioner_info['ip']
