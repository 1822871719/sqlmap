#!/usr/bin/env python

"""
$Id$

Copyright (c) 2006-2011 sqlmap developers (http://sqlmap.sourceforge.net/)
See the file 'doc/COPYING' for copying permission
"""

from lib.core.common import Backend
from lib.core.common import isTechniqueAvailable
from lib.core.common import randomStr
from lib.core.common import safeSQLIdentificatorNaming
from lib.core.common import unsafeSQLIdentificatorNaming
from lib.core.data import conf
from lib.core.data import kb
from lib.core.data import logger
from lib.core.data import queries
from lib.core.dicts import sybaseTypes
from lib.core.enums import PAYLOAD
from lib.core.exception import sqlmapMissingMandatoryOptionException
from lib.core.exception import sqlmapNoneDataException
from plugins.generic.enumeration import Enumeration as GenericEnumeration

class Enumeration(GenericEnumeration):
    def __init__(self):
        GenericEnumeration.__init__(self)

    def getUsers(self):
        infoMsg = "fetching database users"
        logger.info(infoMsg)

        rootQuery = queries[Backend.getIdentifiedDbms()].users

        randStr = randomStr()
        query = rootQuery.inband.query

        if isTechniqueAvailable(PAYLOAD.TECHNIQUE.UNION) or isTechniqueAvailable(PAYLOAD.TECHNIQUE.ERROR) or conf.direct:
            blinds = [False, True]
        else:
            blinds = [True]

        for blind in blinds:
            retVal = self.__pivotDumpTable("(%s) AS %s" % (query, randStr), ['%s.name' % randStr], blind=blind)

            if retVal:
                kb.data.cachedUsers = retVal[0].values()[0]
                break

        return kb.data.cachedUsers

    def getPrivileges(self, *args):
        warnMsg = "on Sybase it is not possible to fetch "
        warnMsg += "database users privileges, sqlmap will check whether "
        warnMsg += "or not the database users are database administrators"
        logger.warn(warnMsg)

        users = []
        areAdmins = set()

        if conf.user:
            users = [ conf.user ]
        elif not len(kb.data.cachedUsers):
            users = self.getUsers()
        else:
            users = kb.data.cachedUsers

        for user in users:
            if user is None:
                continue

            isDba = self.isDba(user)

            if isDba is True:
                areAdmins.add(user)

            kb.data.cachedUsersPrivileges[user] = None

        return ( kb.data.cachedUsersPrivileges, areAdmins )

    def getDbs(self):
        if len(kb.data.cachedDbs) > 0:
            return kb.data.cachedDbs

        infoMsg = "fetching database names"
        logger.info(infoMsg)

        rootQuery = queries[Backend.getIdentifiedDbms()].dbs
        randStr = randomStr()
        query = rootQuery.inband.query

        if isTechniqueAvailable(PAYLOAD.TECHNIQUE.UNION) or isTechniqueAvailable(PAYLOAD.TECHNIQUE.ERROR) or conf.direct:
            blinds = [False, True]
        else:
            blinds = [True]

        for blind in blinds:
            retVal = self.__pivotDumpTable("(%s) AS %s" % (query, randStr), ['%s.name' % randStr], blind=blind)

            if retVal:
                kb.data.cachedDbs = retVal[0].values()[0]
                break

        return kb.data.cachedDbs

    def getTables(self, bruteForce=None):
        if len(kb.data.cachedTables) > 0:
            return kb.data.cachedTables

        self.forceDbmsEnum()

        if conf.db == "CD":
            conf.db = self.getCurrentDb()

        if conf.db:
            dbs = conf.db.split(",")
        else:
            dbs = self.getDbs()

        for db in dbs:
            dbs[dbs.index(db)] = safeSQLIdentificatorNaming(db)

        infoMsg = "fetching tables for database"
        infoMsg += "%s: %s" % ("s" if len(dbs) > 1 else "", ", ".join(db for db in dbs))
        logger.info(infoMsg)

        if isTechniqueAvailable(PAYLOAD.TECHNIQUE.UNION) or isTechniqueAvailable(PAYLOAD.TECHNIQUE.ERROR) or conf.direct:
            blinds = [False, True]
        else:
            blinds = [True]

        for db in dbs:
            for blind in blinds:
                randStr = randomStr()
                query = rootQuery.inband.query % db
                retVal = self.__pivotDumpTable("(%s) AS %s" % (query, randStr), ['%s.name' % randStr], blind=blind)

                if retVal:
                    for table in retVal[0].values()[0]:
                        if not kb.data.cachedTables.has_key(db):
                            kb.data.cachedTables[db] = [table]
                        else:
                            kb.data.cachedTables[db].append(table)
                    break

        return kb.data.cachedTables

    def getColumns(self, onlyColNames=False):
        self.forceDbmsEnum()

        if conf.db is None or conf.db == "CD":
            if conf.db is None:
                warnMsg = "missing database parameter, sqlmap is going "
                warnMsg += "to use the current database to enumerate "
                warnMsg += "table(s) columns"
                logger.warn(warnMsg)

            conf.db = self.getCurrentDb()

        elif conf.db is not None:
            if  ',' in conf.db:
                errMsg = "only one database name is allowed when enumerating "
                errMsg += "the tables' columns"
                raise sqlmapMissingMandatoryOptionException, errMsg

        conf.db = safeSQLIdentificatorNaming(conf.db)

        if conf.tbl:
            tblList = conf.tbl.split(",")
        else:
            self.getTables()

            if len(kb.data.cachedTables) > 0:
                tblList = kb.data.cachedTables.values()

                if isinstance(tblList[0], (set, tuple, list)):
                    tblList = tblList[0]
            else:
                errMsg = "unable to retrieve the tables"
                errMsg += "on database '%s'" % conf.db
                raise sqlmapNoneDataException, errMsg

        for tbl in tblList:
            tblList[tblList.index(tbl)] = safeSQLIdentificatorNaming(tbl)

        rootQuery = queries[Backend.getIdentifiedDbms()].columns

        if isTechniqueAvailable(PAYLOAD.TECHNIQUE.UNION) or isTechniqueAvailable(PAYLOAD.TECHNIQUE.ERROR) or conf.direct:
            blinds = [False, True]
        else:
            blinds = [True]

        for tbl in tblList:
            if conf.db is not None and len(kb.data.cachedColumns) > 0 \
               and conf.db in kb.data.cachedColumns and tbl in \
               kb.data.cachedColumns[conf.db]:
                infoMsg = "fetched tables' columns on "
                infoMsg += "database '%s'" % conf.db
                logger.info(infoMsg)

                return { conf.db: kb.data.cachedColumns[conf.db]}

            infoMsg = "fetching columns "
            infoMsg += "for table '%s' " % tbl
            infoMsg += "on database '%s'" % conf.db
            logger.info(infoMsg)

            for blind in blinds:
                randStr = randomStr()
                query = rootQuery.inband.query % (conf.db, conf.db, conf.db, conf.db, conf.db, conf.db, conf.db, unsafeSQLIdentificatorNaming(tbl))
                retVal = self.__pivotDumpTable("(%s) AS %s" % (query, randStr), ['%s.name' % randStr,'%s.usertype' % randStr], blind=blind)

                if retVal:
                    table = {}
                    columns = {}

                    for name, type_ in zip(retVal[0]["%s.name" % randStr], retVal[0]["%s.usertype" % randStr]):
                        columns[name] = sybaseTypes[type_] if type_ else None

                    table[tbl] = columns
                    kb.data.cachedColumns[conf.db] = table

                    break

        return kb.data.cachedColumns

    def searchDb(self):
        warnMsg = "on Sybase searching of databases is not implemented"
        logger.warn(warnMsg)

        return []

    def searchTable(self):
        warnMsg = "on Sybase searching of tables is not implemented"
        logger.warn(warnMsg)

        return []

    def searchColumn(self):
        warnMsg = "on Sybase searching of columns is not implemented"
        logger.warn(warnMsg)

        return []
