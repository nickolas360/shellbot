#!/usr/bin/env python3
# Copyright (C) 2015 nickolas360 (https://github.com/nickolas360)
# Copyright (C) 2015 Nathan Krantz-Fire (https://github.com/zippynk)
# Added the option -p <prefix>.
#
# This file is part of shellbot.
#
# shellbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# shellbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with shellbot.  If not, see <http://www.gnu.org/licenses/>.
#
# See EXCEPTIONS for additional permissions.
"""
Usage:
  shellbot [options] <host> <port> [<channel>]...
  shellbot -h | --help | --version

Options:
  -n <nickname>    The nickname to use [default: shellbot].
  -m <max-lines>   The maximum number of lines of output to send [default: 10].
  -t <timeout>     How many seconds to wait before killing processes
                   [default: 0.5].
  -p <prefix>      The prefix which identifies commands to run [default: !$].
  -u <user>        Run commands as the specified user. Prevents the shellbot
                   process from being killed. Must be run as root.
  -d <directory>   The current working directory for all commands.
  --queries        Allow shell commands in private queries.
  --password       Set a connection password. Can be used to identify with
                   NickServ. Uses getpass() if stdin is not a TTY.
  --getpass        Force password to be read with getpass().
  --ssl            Use SSL/TLS to connect to the IRC server.
  --cafile <file>  Use the specified list of CA root certificates to
                   verify the IRC server's certificate.
"""
from pyrcb import IRCBot
from command import run_shell
from docopt import docopt
from datetime import datetime
from getpass import getpass
import os
import re
import sys
import threading

__version__ = "0.1.2"

# If modified, replace the source URL with one to the modified version.
help_message = """\
Source: https://github.com/nickolas360/shellbot (AGPLv3 or later)
Use in private queries is {0}.
To run a command, send "{1} <command>".
"""


class Shellbot(IRCBot):
    def __init__(self, lines, timeout, prefix, queries, user, cwd, **kwargs):
        super(Shellbot, self).__init__(**kwargs)
        self.max_lines = lines
        self.timeout = timeout
        self.prefix = prefix
        self.allow_queries = queries
        self.cmd_user = user
        self.cwd = cwd

    def on_query(self, message, nickname):
        if message.lower() == "help":
            response = help_message.format(
                ["disabled", "enabled"][self.allow_queries], self.prefix)
            for line in response.splitlines():
                self.send(nickname, line)
        else:
            self.send(nickname, 'Type "help" for help.')

    def on_message(self, message, nickname, channel, is_query):
        split = message.split(" ", 1)
        if len(split) < 2 or split[0] == self.prefix:
            if is_query:
                self.on_query(message, nickname)
            return
        if is_query and not self.allow_queries:
            self.send(nickname, "Running commands in queries is disabled.")
            return
        print("[{3}] [{0}] <{1}> {2}".format(
            channel or nickname, nickname, message,
            datetime.now().replace(microsecond=0)))
        threading.Thread(
            target=self.run_command,
            args=(split[1], channel or nickname)).start()

    def run_command(self, command, target):
        # Strip ANSI escape sequences.
        lines = [re.sub(r"\x1b.*?[a-zA-Z]", "", l) for l in run_shell(
            command, self.cmd_user, self.cwd, self.timeout, self.timeout / 2)]
        lines = [l for l in lines if l]

        for line in lines[:self.max_lines]:
            self.send(target, line)
            print(">>> " + line)
        if len(lines) > self.max_lines:
            message = "...output trimmed to {0} lines.".format(self.max_lines)
            self.send(target, message)
            print(">>> " + message)
        if not lines:
            message = "Command produced no output."
            self.send(target, message)
            print(">>> " + message)


def main():
    args = docopt(__doc__, version=__version__)
    if args["-u"] and os.geteuid() != 0:
        print('Must be run as root when "-u" is specified.', file=sys.stderr)
        return
    if not args["-u"] and os.geteuid() == 0:
        print('Warning: Running as root without "-u" option.', file=sys.stderr)

    bot = Shellbot(lines=int(args["-m"]), timeout=float(args["-t"]),
                   prefix=args["-p"], queries=args["--queries"],
                   user=args["-u"], cwd=args["-d"])
    bot.connect(args["<host>"], int(args["<port>"]), use_ssl=args["--ssl"],
                ca_certs=args["--cafile"])

    if args["--password"]:
        print("Password: ", end="", file=sys.stderr, flush=True)
        use_getpass = sys.stdin.isatty() or args["--getpass"]
        bot.password(getpass("") if use_getpass else input())
        if not use_getpass:
            print("Received password.", file=sys.stderr)
    bot.register(args["-n"])

    for channel in args["<channel>"]:
        bot.join(channel)
    bot.listen()

if __name__ == "__main__":
    main()
