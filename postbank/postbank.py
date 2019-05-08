# -*- coding: utf-8 -*-
import re
#from discord.ext import commands
from redbot.core import commands
import sqlite3


class InitDb(object):

    def __init__(self, db_file, sql_setup):

        try:
            with open(sql_setup, 'r') as f:
                sql_setup = f.read()
        except (FileNotFoundError, FileNotFoundError) as e:
            print(e)

        self.db_file = db_file
        conn = self.conn_db(db_file)

        if conn is not None:
            self.create_table(conn, sql_setup)
            conn.commit()
            conn.close()

        else:
            print(e)

    def conn_db(self, db_file):
        # Connect to a database
        try:
            conn = sqlite3.connect(db_file)
            return conn
        except Exception as e:
            print(e)

    def create_table(self, conn, create_table_sql):
        # Create the tables IF NOT EXIST.
        try:
            c = conn.cursor()
            c.executescript(create_table_sql)

        except Exception as e:
            print(e)


class PostBank(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.feedback_ids = [{'id': 0, 'user': None}]
        self.bank = bot.get_cog('Economy').bank
        self.db_path = './cogs/postbank.db'  # location of the postbank database file.
        self.db_setup = './cogs/postbank_setup.sql'  # location of the sqlite setup file.
        self.db = InitDb(self.db_path, self.db_setup)  # create the DB if it doesn't exist.
        self.min_length = 140  # Minimum number of characters to be awarded for feedback.

    async def hasAccount(self, user):
        """Creates the users bank account if it doesn't exist. Everyone starts with one credit."""

        hasAccount = self.bank.account_exists(user)
        if hasAccount is True:
            return 0
        else:
            self.bank.create_account(user=user, initial_balance=0)
            return 1

    @commands.command(pass_context=True, no_pm=True)
    async def balance(self, ctx):
        """Gets the credit balance of the user who authors the $balance command, and returns it to the chat."""
        user = ctx.message.author

        await self.hasAccount(user)
        bal = self.bank.get_balance(user)

        await self.bot.send_message(ctx.message.channel, "<@{}>: Your credit balance is: {}".format(user.id, bal))

    @commands.command(pass_context=True, no_pm=True)
    async def edit(self, ctx):
        """Allows you to edit your posted link. $edit <id> <link>"""
        user = ctx.message.author
        content = ctx.message.content.split(" ")
        conn = sqlite3.connect(self.db_path)
        curr = conn.cursor()

        feedbackid = content[1] # get only the feedback ID.
        msg = content[1:]  # Get only the message content and ignore the command parameter
        joined_str = (' '.join(str(x) for x in msg))  # mash this into 1 string
        link = re.search("(?P<url>https?://[^\s]+)", joined_str).group("url")  # Grab only the URL.
        try:
            rows = curr.execute('SELECT userid FROM postbank WHERE feedbackid = ?;', (feedbackid),)
            row = rows.fetchone()

        except Exception as e:
            print("Error in SQL: {}".format(e))

        if user.id == row[0]:
            try:
                curr.execute('UPDATE postbank SET link=? WHERE feedbackid=?;', (link, feedbackid))
                conn.commit()
            except Exception as e:
                print("Error: {}".format(e))

            await self.bot.send_message(ctx.message.channel, "{}: Your link for Posting ID [{}] has been updated".format(user, feedbackid))

        else:
            await self.bot.send_message(ctx.message.channel, "{}: You cannot edit an ID that isn't yours.".format(user))

        conn.close()

    @commands.command(pass_context=True, no_pm=True)
    async def recent(self, ctx):
        """Displays the last 10 posts and whether or not they have any feedback."""
        recents = []
        checkmarkEmoji = u'\U00002705'
        circleEmoji = u'\U00002B55'
        rip = u'\U00002620'
        conn = sqlite3.connect(self.db_path)
        curr = conn.cursor()

        rows = curr.execute('SELECT * FROM postbank LIMIT 10 OFFSET (SELECT COUNT(*) FROM postbank)-10;')
        for row in rows:

            feedbackid = row[0]
            userid = row[1]
            try:
                username = ctx.message.server.get_member(userid).name
            except AttributeError as e:
                # If the user left the server, get_member will throw an attribute error on getting .name
                username = rip+"LEFT THE SERVER"
            link = row[2]

            if row[3] > 0:
                emoji = checkmarkEmoji
            else:
                emoji = circleEmoji
            feedback = "{} -- `{}` -- {} -- <{}>".format(emoji, feedbackid, username, link)
            recents.append(feedback)

        await self.bot.send_message(ctx.message.channel, "\n".join(recents))

    @commands.command(pass_context=True, no_pm=True)
    async def need(self, ctx):
        """Displays the last 10 posts that still need feedback"""
        recents = []
        checkmarkEmoji = u'\U00002705'
        circleEmoji = u'\U00002B55'
        rip = u'\U00002620'
        conn = sqlite3.connect(self.db_path)
        curr = conn.cursor()

        rows = curr.execute('SELECT * FROM postbank WHERE numreviews = 0 LIMIT 10 OFFSET (SELECT COUNT(*) FROM postbank WHERE numreviews = 0)-10;')
        for row in rows:

            feedbackid = row[0]
            userid = row[1]
            try:
                username = ctx.message.server.get_member(userid).name
            except AttributeError as e:
                # If the user left the server, get_member will throw an attribute error on getting .name
                username = rip+"LEFT THE SERVER"
            link = row[2]

            if row[3] > 0:
                emoji = checkmarkEmoji
            else:
                emoji = circleEmoji
            feedback = "{} -- `{}` -- {} -- <{}>".format(emoji, feedbackid, username, link)
            recents.append(feedback)

        await self.bot.send_message(ctx.message.channel, "\n".join(recents))

    @commands.command(pass_context=True, no_pm=True)
    async def post(self, ctx):
        """Lets the user post if the url if they have enough credit.
        Use ReCensor to enforce this rule and remove posts."""
        user = ctx.message.author
        channel = ctx.message.channel
        content = ctx.message.content.split(" ")
        msg = content[1:]  # Get only the message content and ignore the command parameter
        joined_str = (' '.join(str(x) for x in msg))  # mash this into 1 string
        link = re.search("(?P<url>https?://[^\s]+)", joined_str).group("url")  # Grab only the URL.

        await self.hasAccount(user)

        canSpend = self.bank.can_spend(user=user, amount=1)
        bal = self.bank.get_balance(user)

        if canSpend is True:

            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            cur.execute('SELECT * FROM postbank WHERE link=?;', (link,))

            if cur.fetchone() is not None:
                await self.bot.send_message(channel, "<@{}> That link was already submitted.".format(user.id))
                conn.close()
                return

            cur.execute('INSERT INTO postbank (userid, link, numreviews, reviewers) VALUES (?,?,0,?);', (user.id, link,
                                                                                                         '0,1'))
            conn.commit()

            cur.execute('SELECT feedbackid FROM postbank WHERE link=?', (link,))
            rows = cur.fetchall()
            feedback_id = rows[0][0]

            conn.close()
            await self.bot.send_message(channel, "{} submitted a track! Use `$feedback {} <feedback post here>` to give them some feedback!".format(user, feedback_id))
            self.bank.withdraw_credits(user=user, amount=1)

        else:

            await self.bot.send_message(ctx.message.channel, "{}: Your post was removed because you don't have any credit. Give users $feedback to get credit.".format(user.name, bal))
            await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True)
    async def feedback(self, ctx):
        user = ctx.message.author
        await self.hasAccount(user)

        msg = ctx.message.content
        feedback = msg.split(" ")

        feedback_id = feedback[1]
        feedback_text = feedback[2:]
            
        feedback_len = len(" ".join(feedback_text))

        # First check if they are the one that submitted the link. If so, deny them the ability to review themselves.
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute('SELECT userid FROM postbank WHERE feedbackid=?;', (feedback_id,))

        rows = cur.fetchall()

        if rows[0][0] == user.id:
            await self.bot.send_message(ctx.message.channel,
                                        "<@{}>: You cannot review your own submissions.".format(user.id))
            conn.close()
            return

        # Build a list to check against.
        cur.execute('SELECT feedbackid FROM postbank')
        rows = cur.fetchall()
        feedback_id_list = []

        for x in rows:
            feedback_id_list.append(x[0])

        # Then, check if the length meets the minimum requirements and that the ID is valid
        if int(feedback_id) in feedback_id_list:

            if feedback_len < self.min_length:

                await self.bot.send_message(ctx.message.channel, "<@{}>: Your feedback needs to be "
                                                                 "140 characters or greater.".format(user.id))
                conn.close()

            else:

                cur.execute('SELECT reviewers, numreviews, userid FROM postbank WHERE feedbackid=?;', (feedback_id,))
                rows = cur.fetchall()

                reviewers_db = rows[0][0]
                numreviews = rows[0][1]
                op = rows[0][2]

                reviewers = reviewers_db.split(',')

                if user.id not in reviewers:
                    reviewers.append(user.id)
                    reviewers = ','.join(map(str, reviewers))

                    total_reviews = numreviews + 1
                    cur.execute('UPDATE postbank SET numreviews=?,reviewers=? WHERE feedbackid=?;', (total_reviews,
                                                                                                     reviewers,
                                                                                                     feedback_id,))

                    await self.bot.send_message(ctx.message.channel, "<@{}>: You've got feedback!".format(op))

                    self.bank.deposit_credits(user=user, amount=1)

                    conn.commit()
                    conn.close()

                else:
                    await self.bot.send_message(ctx.message.channel, "<@{}>: You already submitted a"
                                                                     " review for this ID.".format(user.id))

        else:

            await self.bot.send_message(ctx.message.channel, "<@{}>: {} is not a valid feedback ID.".format(user.id,feedback_id))
            conn.close()

        conn.close()


def setup(bot):
    n = PostBank(bot)
    bot.add_cog(n)
