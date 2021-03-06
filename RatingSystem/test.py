###
# Copyright (c) 2010, Daniel Folkinshteyn
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

from supybot.test import *

import sqlite3
import time

class RatingSystemTestCase(PluginTestCase):
    plugins = ('RatingSystem','GPG')

    def setUp(self):
        PluginTestCase.setUp(self)
        # pre-seed the db with a rating for nanotube
        cb = self.irc.getCallback('RatingSystem')
        cursor = cb.db.db.cursor()
        cursor.execute("""INSERT INTO users VALUES
                          (NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (10, time.time(), 1, 0, 0, 0, 'nanotube','stuff/somecloak'))
        cb.db.db.commit()

        #preseed the GPG db with a GPG registration and auth for nanotube
        gpg = self.irc.getCallback('GPG')
        gpg.db.register('AAAAAAAAAAAAAAA1', 'AAAAAAAAAAAAAAAAAAA1AAAAAAAAAAAAAAA1',
                    time.time(), 'nanotube')
        gpg.authed_users['nanotube!stuff@stuff/somecloak'] = {'nick':'nanotube'}
        gpg.db.register('AAAAAAAAAAAAAAA2', 'AAAAAAAAAAAAAAAAAAA1AAAAAAAAAAAAAAA2',
                    time.time(), 'registeredguy')
        gpg.db.register('AAAAAAAAAAAAAAA3', 'AAAAAAAAAAAAAAAAAAA1AAAAAAAAAAAAAAA3',
                    time.time(), 'authedguy')
        gpg.authed_users['authedguy!stuff@123.345.234.34'] = {'nick':'authedguy'}
        gpg.db.register('AAAAAAAAAAAAAAA4', 'AAAAAAAAAAAAAAAAAAA1AAAAAAAAAAAAAAA4',
                    time.time(), 'authedguy2')
        gpg.authed_users['authedguy2!stuff@123.345.234.34'] = {'nick':'authedguy2'}

    def testRate(self):
        self.assertError('rate someguy 4') # not authenticated
        try:
            origuser = self.prefix
            self.prefix = 'nanotube!stuff@stuff/somecloak'
            self.assertError('rate nanotube 10') #can't self-rate
            self.assertError('rate nanOtube 10') #can't self-rate
            self.assertError('rate unknownguy 4') #user not in db and not authed
            self.assertRegexp('rate registeredguy 4', 'rating of 4 for user registeredguy has been recorded')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of 4')
            self.assertRegexp('getrating registeredguy', 'a total of 1')
            self.assertRegexp('rate registeredguy 6', 'changed from 4 to 6')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of 6')
            self.assertRegexp('getrating registeredguy', 'a total of 1')
            self.assertRegexp('getrating nanotube', 'sent 1 positive')
            self.assertError('rate registeredguy 0') # rating must be in bounds, and no zeros
            self.assertError('rate registeredguy -20')
            self.assertError('rate registeredguy 30')
            self.assertNotError('rate registeredguy -10')
            self.assertNotError('rate authedguy 5')
            self.assertNotError('rate authedguy2 -1')
            self.assertRegexp('getrating nanotube', 'sent 1 positive ratings, and 2 negative')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of -10')
            self.prefix = 'authedguy!stuff@123.345.234.34'
            self.assertNotError('rate registeredguy 9')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of -1')
            self.prefix = 'registeredguy!stuff@stuff/somecloak'
            self.assertError('rate nanotube 2') # unauthed, can't rate
            self.prefix = 'authedguy2!stuff@123.345.234.34'
            self.assertError('rate nanotube 2') # rated -1, can't rate
            self.prefix = 'nanotube!stuff@stuff/somecloak'
            self.assertNotError('unrate registeredguy')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of 9')
            self.assertRegexp('getrating nanotube', 'and 1 negative ratings to others')
            self.assertNotError('rate registeredGUY 5')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of 14')
            self.assertError('rated nobody')
            self.assertRegexp('rated registeredguy', 'You rated user registeredguy .* giving him a rating of 5')
        finally:
            self.prefix = origuser

    def testUnrate(self):
        try:
            origuser = self.prefix
            self.prefix = 'nanotube!stuff@stuff/somecloak'
            self.assertError('unrate someguy') #haven't rated him before
            self.assertError('unrate registeredguy') #haven't rated him before
            self.assertNotError('rate registeredguy 4')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of 4')
            self.assertNotError('unrate regISTEredguy')
            self.assertError('getrating registeredguy') # guy should be gone, having no connections.
        finally:
            self.prefix = origuser

    def testGetTrust(self):
        try:
            origuser = self.prefix
            self.prefix = 'nanotube!stuff@stuff/somecloak'
            self.assertNotError('rate authedguy 5')
            self.prefix = 'authedguy!stuff@123.345.234.34'
            self.assertNotError('rate authedguy2 3')
            self.assertRegexp('gettrust nanotube authedguy2', 
                        'second-level trust from user nanotube to user authedguy2 is 3')
            self.assertNotError('rate authedguy2 7')
            self.assertRegexp('gettrust nanotube authedguy2', 
                        'second-level trust from user nanotube to user authedguy2 is 5')
            self.prefix = 'nanotube!stuff@stuff/somecloak'
            self.assertRegexp('gettrust authedguy2', 
                        'second-level trust from user nanotube to user authedguy2 is 5.*via 1.*level one rating is None')
            self.assertNotError('rate authedguy -1')
            self.assertNotError('rate authedguy2 7')
            self.assertRegexp('gettrust authedguy2', 
                        'second-level trust from user nanotube to user authedguy2 is -1.*via 1.*level one rating is 7')
            self.assertRegexp('gettrust nobody nobody2', 'nobody2 is None.*rating is None')
            self.prefix = 'randomguy!stuff@stuff/somecloak'
            self.assertRegexp('gettrust authedguy2', 'authedguy2 is None.*rating is None')
        finally:
            self.prefix = origuser

    def testDeleteUser(self):
        try:
            origuser = self.prefix
            self.prefix = 'nanotube!stuff@stuff/somecloak'
            self.assertNotError('rate registeredguy 4')
            self.assertRegexp('getrating registeredguy', 'cumulative rating of 4')
            self.assertNotError('deleteuser registeredGUy')
            self.assertError('getrating registeredguy') # guy should be gone
        finally:
            self.prefix = origuser


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
