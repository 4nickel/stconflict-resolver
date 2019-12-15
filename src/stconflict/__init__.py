#!/usr/bin/env python3

import os
import re
import argparse
import datetime
import subprocess
import hashlib


class ConflictFile:
    """
    Syncthing conflict file.
    These are the files that follow the naming scheme `.sync-conflict-$date-$time-$uid`
    """

    UID = r'(?P<uid>[0-9A-Z]{7})'
    DATE = r'(?P<dy>[0-9]{4})(?P<dm>[0-9]{2})(?P<dd>[0-9]{2})'
    TIME = r'(?P<th>[0-9]{2})(?P<tm>[0-9]{2})(?P<ts>[0-9]{2})'

    def __init__(self, path, base, name, conflicts):
        self.path = path
        self.base = base
        self.name = name
        self.conflicts = conflicts

        #
        # Selected: the current selected-visible version of the file.
        # Original: the original file this version was based on.
        #
        # Keep in mind conflicts may be recursive, so it is possible
        # and likely that selected == original.
        #
        self.selected, self.ext = os.path.splitext(
            Conflict.REGEX.sub('', name))
        self.original = self.format(conflicts=self.conflicts[:-1], ext='')
        self.root = self.original == self.selected

        assert self.name == str(self)
        self.parent = None
        self.children = []

    def __repr__(self):
        return self.format()

    def format(self, name=None, conflicts=None, ext=None):
        """Format this conflicts file name."""
        if conflicts is None:
            conflicts = self.conflicts
        if ext is None:
            ext = self.ext
        if name is None:
            name = self.selected
        return '{}{}{}'.format(name, Conflict.format(conflicts), ext)

    def set_parent(self, parent):
        """Set this conflicts parent conflict."""
        assert self.parent is None
        self.parent = parent

        assert not self in parent.children
        parent.children.append(self)

    def age_in_seconds(self):
        """Get this files age in seconds."""
        return Timestamp.file_age(self)

    def top(self):
        """Get this files relevant/top conflict."""
        return self.conflicts[-1]

    def order(self):
        """Get this files order metric."""
        return self.top().order()

    def canonical_name(self):
        """Return the canonical name of this file."""
        return os.path.join(os.path.realpath(self.base), self.name)

    def canonical_selected(self):
        """Return the canonical name of this file's selected version."""
        return os.path.join(os.path.realpath(self.base),
                            self.format(name=self.selected, conflicts=[]))

    def canonical_original(self):
        """Return the canonical name of this file's original version."""
        return os.path.join(os.path.realpath(self.base),
                            self.format(name=self.original, conflicts=[]))

    def canonical_backup(self, args):
        """Return the canonical name of this file's backup version."""
        return os.path.join(self.backup_directory(args), self.name)

    def backup_directory(self, args):
        """Return the path to the backup directory."""
        return os.path.join(self.path, args.backup_dir)

    def timestamp(self):
        """Return the timestamp of this conflict file."""
        return self.top().timestamp

    def delete(self, args):
        """Delete this file."""
        if args.commit:
            os.remove(self.canonical_name())
        else:
            print('delete: {}'.format(self.name))

    def backup(self, args):
        """Backup this file."""
        if args.commit:
            if not os.path.isdir(self.backup_directory(args)):
                os.mkdir(self.backup_directory(args))
            os.rename(self.canonical_name(), self.canonical_backup(args))
        else:
            print('backup: {}'.format(self.name))

    @staticmethod
    def show_file(path, _args):
        """Print a file to stdout."""
        try:
            with open(path, 'r') as fd:
                txt = fd.read()
                print(txt[:-1])
        except OSError as e:
            print('failed to show file: {}'.format(path))
            print(str(e))

    @staticmethod
    def show_diff(file_a, file_b, _args):
        """Print the diff of current and conflict version."""
        command = ['diff', '--side-by-side', file_a, file_b]
        try:
            print('>>> running {}'.format(command))
            process, (out, err) = ConflictFile.shell(command)
            if process.returncode in [0, 1]:
                txt = out.decode('utf-8')
                print('<<< stdout')
                print(txt[:-1])
                print('>>>')
            else:
                txt = err.decode('utf-8')
                print('<<< stderr')
                print(txt[:-1])
                print('>>>')
        except OSError:
            print('error: failed to run command: {}'.format(command))

    @staticmethod
    def shell(command):
        """Run a command in a shell and open pipes for communication."""
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return process, process.communicate()

    def prompt(self, args):
        """Run a command in a shell and open pipes for communication."""
        exit_loop = False
        while not exit_loop:
            canonical_name = self.canonical_name()
            canonical_time = self.timestamp().format()
            original = self.canonical_original()
            selected = self.canonical_selected()
            original_time = ' ROOT ' if self.root else self.parent.timestamp().format()
            print('')
            print('--- PROMPT ---')
            print('[{}] {}'.format(canonical_time, self.name))
            print('[{}] {}'.format(original_time, '{}{}'.format(self.original, self.ext)))
            print('---')
            print('sc: show conflict file')
            print('so: show original file')
            print('sb: show base file')
            print('kc: keep conflict file')
            print('ko: keep original file')
            print('kb: keep base file')
            print('do: diff conflict/original')
            print('db: diff conflict/base')
            print('qq: quit')
            print('---')
            i = input('>>> ')
            i = i[:2]
            if i == 'sc':
                ConflictFile.show_file(canonical_name, args)
            elif i == 'so':
                ConflictFile.show_file(original, args)
            elif i == 'sb':
                ConflictFile.show_file(selected, args)
            elif i == 'kc':
                ConflictFile.show_file(canonical_name, args)
            elif i == 'ko':
                ConflictFile.show_file(original, args)
            elif i == 'kb':
                ConflictFile.show_file(selected, args)
            elif i == 'do':
                ConflictFile.show_diff(original, canonical_name, args)
            elif i == 'db':
                ConflictFile.show_diff(selected, canonical_name, args)
            elif i == 'qq':
                exit_loop = True


class Date:
    """A date: year, month and day."""

    def __init__(self, yy, mm, dd):
        self.yy = int(yy)
        self.mm = int(mm)
        self.dd = int(dd)

    def __repr__(self):
        """Same as syncthings date representation."""
        return '{:>04}{:>02}{:>02}'.format(self.yy, self.mm, self.dd)

    def order(self):
        """Calculate order metric for this date."""
        return self.yy * 356 * + self.mm * 30 + self.dd


class Time:
    """Clock-time: hour, minute and second."""

    def __init__(self, hh, mm, ss):
        self.hh = int(hh)
        self.mm = int(mm)
        self.ss = int(ss)

    def __repr__(self):
        """Same as syncthings time representation."""
        return '{:>02}{:>02}{:>02}'.format(self.hh, self.mm, self.ss)

    def order(self):
        """Calculate order metric for this time."""
        return self.hh * 60*60 + self.mm * 60 + self.ss


class Timestamp:
    """A date and a clocktime form a datetime."""

    NOW = None

    def __init__(self, date, time):
        self.date = date
        self.time = time
        self.dt = datetime.datetime(
            date.yy, date.mm, date.dd,
            time.hh, time.mm, time.ss
        )

    def __repr__(self):
        return '{}{}'.format(self.date, self.time)

    @staticmethod
    def from_dt(dt):
        """Create a new instance from a datetime."""
        date = Date(dt.year, dt.month, dt.day)
        time = Time(dt.hour, dt.minute, dt.second)
        return Timestamp(date, time)

    @staticmethod
    def now():
        """Get the current time as unix timestamp."""
        if not Timestamp.NOW:
            Timestamp.NOW = Timestamp.from_dt(datetime.datetime.now())
        return Timestamp.NOW

    @staticmethod
    def file_age(conflict_file):
        """Get the files current time as unix timestamp."""
        return Timestamp.delta(Timestamp.now(), conflict_file.top().timestamp)

    def order(self):
        """Get the order metric for this timestamp."""
        return int(str(self))

    def delta(self, other):
        """Get the time difference between this timestamp and another."""
        return (self.dt - other.dt).total_seconds()

    def format(self):
        """Format this timestamp to a string."""
        return self.dt.strftime('%b %d')


class Conflict:
    """Conflict description."""

    REGEX = re.compile(
        r'\.sync-conflict-({})-({})-({})'.format(
            ConflictFile.DATE,
            ConflictFile.TIME,
            ConflictFile.UID
        )
    )

    def __init__(self, date, time, uid):
        self.date = Date(*date)
        self.time = Time(*time)
        self.uid = uid
        self.timestamp = Timestamp(self.date, self.time)

    def __repr__(self):
        """Same as syncthings represention of the conflict."""
        return '.sync-conflict-{}-{}-{}'.format(self.date, self.time, self.uid)

    def order(self):
        """Order conflicts chronologically"""
        return self.timestamp.order()

    @staticmethod
    def format(conflicts):
        """Helper function to format a list of conflicts."""
        s = ''
        for c in conflicts:
            s = '{}{}'.format(s, c)
        return s

    @staticmethod
    def parse(path):
        """Extract conflict data from file name."""
        conflicts = []
        for c in Conflict.REGEX.finditer(path):
            date = (c.group('dy'), c.group('dm'), c.group('dd'))
            time = (c.group('th'), c.group('tm'), c.group('ts'))
            uid = c.group('uid')
            conflicts.append(Conflict(date, time, uid))
        return conflicts


class Heuristic:
    """Implements heuristics in order to recommend actions."""

    NONE = 0
    OLD = 1
    SAME = 2
    NESTED = 3
    ORPHANED = 4
    OBSOLETE = 5
    YOUNG = 6

    @staticmethod
    def is_old(conflict_file, _args):
        """Check if a conflict is considered stale."""
        days_threshold = 30
        return conflict_file.age_in_seconds() > days_threshold * 60*60*24

    @staticmethod
    def is_young(conflict_file, _args):
        """Check if a conflict is considered fresh."""
        days_threshold = 5
        return conflict_file.age_in_seconds() < days_threshold * 60*60*24

    @staticmethod
    def is_same(conflict_file, _args):
        """Check if a conflict exactly matches the original (shouldn't happen but can't hurt)."""
        selected = conflict_file.canonical_selected()
        original = conflict_file.canonical_original()
        with open(selected, "r") as fselected:
            with open(original, "r") as foriginal:
                selected_digest = hashlib.sha256()
                original_digest = hashlib.sha256()
                for line in fselected:
                    selected_digest.update(line)
                for line in foriginal:
                    original_digest.update(line)
                return selected_digest.digest() == original_digest.digest()
        return False

    @staticmethod
    def is_nested(conflict_file, _args):
        """Check if a conflict is based on another conflict."""
        return conflict_file.parent is not None

    @staticmethod
    def is_orphan(conflict_file, _args):
        """Check if a conflict's original file has vanished."""
        return not os.path.isfile(conflict_file.canonical_original())

    @staticmethod
    def is_obsolete(conflict_file, _args):
        """Check if a conflict's base file has vanished."""
        return not os.path.isfile(conflict_file.canonical_selected())

    @staticmethod
    def check(conflict_file, args):
        """Check heuristics one-by-one."""
        mapping = {
            Heuristic.OLD:      Heuristic.is_old,
            Heuristic.OBSOLETE: Heuristic.is_obsolete,
            Heuristic.SAME:     Heuristic.is_same,
            Heuristic.ORPHANED: Heuristic.is_orphan,
            Heuristic.NESTED:   Heuristic.is_nested,
            Heuristic.YOUNG:    Heuristic.is_young,
        }
        for i, heuristic in mapping.items():
            if heuristic(conflict_file, args):
                return i
        return Heuristic.NONE


class Action:
    """Implements actions to resolve conflicts."""

    DELETE = 0
    BACKUP = 1
    PROMPT = 2

    NAMES = {
        DELETE: "DELETE",
        BACKUP: "BACKUP",
        PROMPT: "PROMPT",
    }

    @staticmethod
    def mapping(heuristic):
        """Generate the mapping [Heuristic -> Action]."""
        mapping = {
            Heuristic.OLD:      Action.DELETE,
            Heuristic.SAME:     Action.DELETE,
            Heuristic.NESTED:   Action.DELETE,
            Heuristic.OBSOLETE: Action.DELETE,
            Heuristic.ORPHANED: Action.DELETE,
            Heuristic.YOUNG:    Action.PROMPT,
            Heuristic.NONE:     Action.BACKUP,
        }
        return mapping[heuristic]

    @staticmethod
    def delete(conflict_file, args):
        """Delete action."""
        conflict_file.delete(args)

    @staticmethod
    def backup(conflict_file, args):
        """Backup action."""
        conflict_file.backup(args)

    @staticmethod
    def prompt(conflict_file, args):
        """Prompt action."""
        conflict_file.prompt(args)

    @staticmethod
    def run(conflict_file, action, args):
        """Run the action mapped to the heuristics result."""
        call = ACTION_MAP[action]
        call(conflict_file, args)


ACTION_MAP = {
    Action.DELETE: Action.delete,
    Action.BACKUP: Action.backup,
    Action.PROMPT: Action.prompt,
}


class Cli:
    """Command-line interface."""

    def __init__(self, args):
        self.args = args

    def scan_for_conflicts(self):
        """Scan all provided paths for conflicts."""
        scan = []
        for path in self.args.PATH:
            assert os.path.isdir(os.path.join(path, '.stfolder'))
            for base, directories, files in os.walk(path):
                if self.args.backup_dir in directories:
                    directories.remove(self.args.backup_dir)
                for name in files:
                    conflicts = Conflict.parse(name)
                    if conflicts:
                        scan.append(ConflictFile(
                            path, base, name, conflicts))
        return scan

    def conflict_map(self, scan):
        """Map path name -> file conflict object."""
        assert self
        conflict_map = {}
        for conflict_file in scan:
            conflict_map[conflict_file.canonical_name()] = conflict_file
        return conflict_map

    def conflict_tree(self, conflict_map):
        """Graph conflicts into tree structure."""
        assert self
        conflict_tree = []
        for _, conflict_file in conflict_map.items():
            if conflict_file.root:
                assert not conflict_file in conflict_tree
                conflict_tree.append(conflict_file)
            else:
                original = conflict_map[conflict_file.canonical_original()]
                conflict_file.set_parent(original)
        return conflict_tree

    def actions(self, conflict_map):
        """Generate list of actions for the given conflicts."""
        actions = [[], [], []]
        for _, conflict_file in conflict_map.items():
            action = Action.mapping(Heuristic.check(conflict_file, self.args))
            actions[action].append(conflict_file)
        return actions

    def report(self, actions):
        """Generate a report of actions to take."""
        assert self
        ORDER = [Action.DELETE, Action.BACKUP, Action.PROMPT]
        for index, action in enumerate(ORDER):
            if index > 0:
                print('')
            print('[{}] {} files total'.format(
                Action.NAMES[action], len(actions[action])))
            for f in actions[action]:
                print(f)

    def run(self):
        """Main routine and entry point."""
        # The process is simple:
        #   1. Scan for conflicts
        #   2. Apply heuristics
        #   3. Run the associated actions

        conflict_map = self.conflict_map(self.scan_for_conflicts())
        _conflict_tree = self.conflict_tree(conflict_map)
        actions = self.actions(conflict_map)
        self.report(actions)
        for f in actions[Action.PROMPT]:
            f.prompt(self.args)


def stconflict_cli():
    """Main entry point."""

    description = 'syncthing conflict resolver'
    version = '0.1'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--version', action='version',
                        version=version, help='print version and exit')
    parser.add_argument('--backup-dir', type=str,
                        help='location to back up to', default='.stbackups')
    parser.add_argument('--version-dir', type=str,
                        help='location to back up to', default='.stversions')
    parser.add_argument('--commit', action='store_true',
                        help='actually run commands')
    parser.add_argument('PATH', type=str, help='path specification', nargs='*')
    args = parser.parse_args()
    cli = Cli(args)
    cli.run()

if __name__ == "main":
    stconflict_cli()
