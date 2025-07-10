"""The cleversheep3 test framework journal.

The journal is used to record execution details for each test. It stores a
history of test runs, which can be queried and managed using the `cst`
program.

"""
__docformat__ = "restructuredtext"


import os
import time
import struct
import pickle
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5

from cleversheep3.Prog import Files
from cleversheep3.Test.Tester import Core
from cleversheep3.Test.Tester import options

_journalPath = os.path.abspath(".csdata/test_journal.bin")

class Journal:
    """A class to manage the test execution journal.

    """
    def __init__(self):
        self.problems = {}
        self.hdrFmt = ">I16sI"
        self.hdrLen = struct.calcsize(self.hdrFmt)

    def loadRc(self):
        self.maxAge = None
        self.maxRecords = 4
        d = {}
        execPath = os.path.expanduser("~/.csrc")
        try:
            with open(execPath) as f:
                code = compile(f.read(), metaPath, 'exec')
                exec(code, d, )
        except: # TODO: Mega-shame!
            return
        self.maxAge = d.get("maxJournalAge", self.maxAge)
        self.maxRecords = d.get("maxTestRecords", self.maxRecords)

    def fix(self, collecton):
        if not options.enable_journal:
            return
        if not os.path.exists(_journalPath):
            return
        self.f = open(_journalPath, "rb")
        records = []
        while True:
            rec, rawRecord = self.loadRecord()
            if rec is None:
                break
            records.append(rec)

        for record in records:
            self._save(record, "fixed.bin")

    def load(self, collection):
        if not options.enable_journal:
            return
        self.buf = ""
        if not os.path.exists(_journalPath):
            return
        tmpPath = _journalPath + ".tmp"
        os.rename(_journalPath, tmpPath)

        self.loadRc()
        now = time.time()
        toDiscard = set()
        seenCounts = {}
        kept, discarded = 0, 0

        # Scan the journal to figure what to keep.
        count = 0
        self.f = open(tmpPath, "rb")
        while True:
            record, rawRecord = self.loadRecord()
            if not record:
                break
            ver, uid, runRecord = record
            if runRecord is None:
                continue  # Handles slightly broken older code.
            count += 1
            if self.maxAge is not None and now - runRecord.runTime > self.maxAge:
                toDiscard.add(count)
            else:
                seenCounts.setdefault(uid, [])
                sc = seenCounts[uid]
                sc.append(count)
                if len(sc) > self.maxRecords:
                    toDiscard.add(sc.pop(0))

        # Load and keep the wanted records.
        Files.mkParentDir(_journalPath)
        count = 0
        self.f = open(tmpPath, "rb")
        newF = open(_journalPath, "wb")
        while True:
            record, rawRecord = self.loadRecord()
            if not record:
                break
            ver, uid, runRecord = record
            if runRecord is None:
                continue  # Handles slightly broken older code.

            count += 1
            #if count % 100 == 0:
            #    print "Processed %d records" % count
            if count in toDiscard:
                discarded += 1
                continue

            kept += 1
            self._saveRawRec(rawRecord, newF)
            test = collection.getItemByUid(uid)
            if test is not None:
                if runRecord.state != Core.NOT_RUN:
                    test.addRunRecord(runRecord)
        del self.buf
        os.unlink(tmpPath)
        #print "Journal: Loaded %d, discarded %d, kept %d" % (
        #        count, discarded, kept)

    def _getMoreBuf(self):
        s = self.f.read(65536)
        if not s:
            return
        self.buf += s
        return True

    def _tryLoad(self):
        # Make sure we have enough to decode the header part.
        if len(self.buf) < self.hdrLen:
            if not self._getMoreBuf():
                self.problems.setdefault("eof", 0)
                self.problems["eof"] += 1
                return None, None

        magic, digest, rLen = struct.unpack(self.hdrFmt, self.buf[:self.hdrLen])
        if magic != 0xdeadbeef:
            self.problems.setdefault("magic", 0)
            self.problems["magic"] += 1
            return False, None

        # Make sure we have enough buffered to decode the pickled body.
        while len(self.buf) - self.hdrLen < rLen:
            if not self._getMoreBuf():
                self.problems.setdefault("eof", 0)
                self.problems["eof"] += 1
                return None, None

        pickleRec = self.buf[self.hdrLen:self.hdrLen + rLen]
        rawRecord = magic, digest, rLen, pickleRec
        sum = md5(pickleRec)
        if sum.digest() != digest:
            self.problems.setdefault("sum", 0)
            self.problems["sum"] += 1
            return False, rawRecord

        try:
            ret = pickle.loads(pickleRec)
        except pickle.UnpicklingError:
            self.problems.setdefault("pickle", 0)
            self.problems["pickle"] += 1
            return False, rawRecord
        except TypeError as exc:
            self.problems.setdefault("type", 0)
            self.problems["type"] += 1
            return False, rawRecord
        else:
            # Move the input buffer onto the next record.
            self.buf = self.buf[self.hdrLen + rLen:]

        return ret, rawRecord

    def resync(self):
        """Attempt to resync with the next record in the journal.

        This is invoked when a journal read failure occurs.

        """
        #print "Resync @", self.f.tell()
        mStr = struct.pack(">I", 0xdeadbeef)
        self.buf = self.buf[1:]
        while True:
            self._getMoreBuf()
            if len(self.buf) < self.hdrLen:
                return False
            i = self.buf.find(mStr)
            if i >= 0:
                # Found it, move to the start of the magic number.
                self.buf = self.buf[i:]
                return True

            # Keep the last 4 bytes and try again.
            self.buf = self.buf[-4:]

    def loadRecord(self):
        import sys
        count = 0
        try:
            while True:
                rec, rawRecord = self._tryLoad()
                if rec is None:
                    return None, rawRecord
                elif rec:
                    return rec, rawRecord
                count += 1
                if not self.resync():
                    return None, None
            return rec
        finally:
            if count:
                pass
                #print "Seek count = %d" % count
                #print self.problems

    def _saveRawRec(self, rawRecord, f):
        magic, cx, length, pickleRec = rawRecord
        fmt = ">I16sL%ds" % len(pickleRec)
        record = struct.pack(fmt, magic, cx, length, pickleRec)
        f.write(record)

    def _saveRec(self, journalRec, f):
        pickleRec = pickle.dumps(journalRec, -1)
        sum = md5(pickleRec)
        self._saveRawRec(
                (0xdeadbeef, sum.digest(), len(pickleRec), pickleRec), f)

    def _save(self, journalRec, path):
        if not options.enable_journal:
            return
        Files.mkParentDir(_journalPath)
        if os.path.exists(_journalPath):
            f = open(path, "ab+")
        else:
            f = open(path, "wb")
        try:
            self._saveRec(journalRec, f)
        finally:
            f.close()

    def record(self, test, path=None):
        """We store records in the following format::

          0           4        20          24
         +--+--+--+--+--+- - -+--+--+--+--+--+--+--+--+--+--+- - - +--+--+
         |DE AD BE EF|MD5 sum |  length   | Pickled record               |
         +--+--+--+--+--+- - -+--+--+--+--+--+--+--+--+--+--+- - - +--+--+

        The magic number 0xDEADBEEF is used to try and re-sync if the input
        data is corrupted. The MD5 sum protects the pickled record.

        """
        ver = 1
        rec = test.runRecord
        if rec is None:
            return
        journalRec = ver, test.uid, rec
        self._save(journalRec, path or _journalPath)


_journal = None

def getJournal():
    global _journal
    if _journal is None:
        _journal = Journal()
    return _journal
