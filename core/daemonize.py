# #!/usr/bin/python

import fcntl
import os
import time
import pwd
import grp
import sys
import signal
import resource
import logging
import atexit
from logging import handlers
import traceback


__version__ = "2.4.7"


class Daemonize(object):
    """
    Daemonize object.

    Object constructor expects three arguments.

    :param app: contains the application name which will be sent to syslog.
    :param pid: path to the pidfile.
    :param action: your custom function which will be executed after daemonization.
    :param keep_fds: optional list of fds which should not be closed.
    :param auto_close_fds: optional parameter to not close opened fds.
    :param args: action parameter.
    :param user: drop privileges to this user if provided.
    :param group: drop privileges to this group if provided.
    :param verbose: send debug messages to logger if provided.
    :param logger: use this logger object instead of creating new one, if provided.
    :param foreground: stay in foreground; do not fork (for debugging)
    :param chdir: change working directory if provided or /
    """
    def __init__(self, app, pid, action,
                 keep_fds=None, auto_close_fds=True, args=[],
                  verbose=False, logger=None,
                 foreground=False, chdir="/"):
        self.app = app
        self.pid = os.path.abspath(pid)
        self.action = action
        self.args = args
        self.logger = logger
        self.keep_fds = []
        self.verbose = verbose
        self.auto_close_fds = auto_close_fds
        self.foreground = foreground
        self.chdir = chdir

    def sigterm(self, signum, frame):
        """
        These actions will be done after SIGTERM.
        """
        self.logger.warn("Caught signal %s. Stopping daemon." % signum)
        sys.exit(0)

    def exit(self):
        """
        Cleanup pid file at exit.
        """
        self.logger.warn("Stopping daemon.")
        os.remove(self.pid)
        sys.exit(0)

    def start(self):
        """
        Start daemonization process.
        """
        # If pidfile already exists, we should read pid from there; to overwrite it, if locking
        # will fail, because locking attempt somehow purges the file contents.
        if os.path.isfile(self.pid):
            with open(self.pid, "r") as old_pidfile:
                old_pid = old_pidfile.read()
        # Create a lockfile so that only one instance of this daemon is running at any time.
        try:
            lockfile = open(self.pid, "w")
        except IOError:
            print("Unable to create the pidfile.")
            sys.exit(1)
        try:
            # Try to get an exclusive lock on the file. This will fail if another process has the file
            # locked.
            fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("Unable to lock on the pidfile.")
            # We need to overwrite the pidfile if we got here.
            with open(self.pid, "w") as pidfile:
                pidfile.write(old_pid)
            sys.exit(1)

        # skip fork if foreground is specified
        if not self.foreground:
            # Fork, creating a new process for the child.
            try:
                process_id = os.fork()
            except OSError as e:
                self.logger.error("Unable to fork, errno: {0}".format(e.errno))
                sys.exit(1)
            if process_id != 0:
                # This is the parent process. Exit without cleanup,
                # see https://github.com/thesharp/daemonize/issues/46
                os._exit(0)
            # This is the child process. Continue.

            # Stop listening for signals that the parent process receives.
            # This is done by getting a new process id.
            # setpgrp() is an alternative to setsid().
            # setsid puts the process in a new parent group and detaches its controlling terminal.
            process_id = os.setsid()
            if process_id == -1:
                # Uh oh, there was a problem.
                sys.exit(1)

            # Add lockfile to self.keep_fds.
            self.keep_fds.append(lockfile.fileno())

            # Close all file descriptors, except the ones mentioned in self.keep_fds.
            devnull = "/dev/null"
            if hasattr(os, "devnull"):
                # Python has set os.devnull on this system, use it instead as it might be different
                # than /dev/null.
                devnull = os.devnull

            if self.auto_close_fds:
                for fd in range(3, resource.getrlimit(resource.RLIMIT_NOFILE)[0]):
                    if fd not in self.keep_fds:
                        try:
                            os.close(fd)
                        except OSError:
                            pass

            devnull_fd = os.open(devnull, os.O_RDWR)
            os.dup2(devnull_fd, 0)
            os.dup2(devnull_fd, 1)
            os.dup2(devnull_fd, 2)
            os.close(devnull_fd)

        if self.logger is None:
            # Initialize logging.
            self.logger = logging.getLogger(self.app)
            self.logger.setLevel(logging.DEBUG)
            # Display log messages only on defined handlers.
            self.logger.propagate = False

            # Initialize syslog.
            # It will correctly work on OS X, Linux and FreeBSD.
            if sys.platform == "darwin":
                syslog_address = "/var/run/syslog"
            else:
                syslog_address = "/dev/log"

            # We will continue with syslog initialization only if actually have such capabilities
            # on the machine we are running this.
            if os.path.exists(syslog_address):
                syslog = handlers.SysLogHandler(syslog_address)
                if self.verbose:
                    syslog.setLevel(logging.DEBUG)
                else:
                    syslog.setLevel(logging.INFO)
                # Try to mimic to normal syslog messages.
                formatter = logging.Formatter("%(asctime)s %(name)s: %(message)s",
                                              "%b %e %H:%M:%S")
                syslog.setFormatter(formatter)

                self.logger.addHandler(syslog)

        # Set umask to default to safe file permissions when running as a root daemon. 027 is an
        # octal number which we are typing as 0o27 for Python3 compatibility.
        os.umask(0o27)

        # Change to a known directory. If this isn't done, starting a daemon in a subdirectory that
        # needs to be deleted results in "directory busy" errors.
        os.chdir(self.chdir)

        # Set custom action on SIGTERM.
        signal.signal(signal.SIGTERM, self.sigterm)
        atexit.register(self.exit)

        self.logger.warn("Starting daemon.")

        try:
            self.action(*self.args)
        except Exception:
            for line in traceback.format_exc().split("\n"):
                self.logger.error(line)
    def getpid(self):
        try:
            pid_list = os.popen("ps -efL|grep -P httpmonitor | grep -v grep | awk '{print $2}'").read().split('\n')
        except Exception:
            pid_list = None
        return pid_list
    def stop(self):
        '''
        Stop daemonization process
        '''
        pid_list = self.getpid()
        if not pid_list:
            message = "pidfile %s does not exist. Not running?\n"
            sys.stderr.write(message % self.pid)
        try:
            for pid in pid_list:
                if pid:
                    os.kill(int(pid), signal.SIGTERM)
        except Exception as e:
            pass
    def restart(self):
        self.stop()
        self.start()
