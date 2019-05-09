# -*- coding: utf-8 -*-
import re
import os
from redbot.core import commands, bank
from redbot.core import Config
import sqlite3
import asyncio


class InitDb(object):

    def __init__(self, db_file):

        try:
            postban_dir = os.path.expanduser('~/.postbank')
            os.mkdir(postban_dir)
        except FileExistsError:
            # Do nothing if the directory exists.
            pass

        sql_setup = """CREATE TABLE
IF NOT EXISTS postbank (
  feedbackid INTEGER PRIMARY KEY AUTOINCREMENT,
  userid TEXT NOT NULL,
  link TEXT NOT NULL,
  numreviews INTEGER,
  reviewers TEXT NOT NULL
);"""
        conn = self.conn_db(db_file)
        if conn is not None:
            self.create_table(conn, sql_setup)
            conn.commit()
            conn.close()
        else:
            print(f"Could not connect to database at {db_file}")

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

        _DEFAULT_GUILD = {
            "bank_name": "PostBank",
            "currency": "credits",
            "default_balance": 1}
        _DEFAULT_GLOBAL = {
            "is_global": False,
            "bank_name": "PostBank",
            "currency": "credits",
            "default_balance": 1,
        }

        self.bot = bot
        self.feedback_ids = [{'id': 0, 'user': None}]
        self.db_path = os.path.expanduser('~/.postbank/postbank.db')  # location of the postbank database file.
        self.db = InitDb(self.db_path)  # create the DB if it doesn't exist.
        self.min_length = 140  # Minimum number of characters to be awarded for feedback.
        self.config = Config.get_conf(self, identifier=384734293238749)
        self.config.register_global(**_DEFAULT_GLOBAL)
        self.config.register_guild(**_DEFAULT_GUILD)

    def default_balance(self, amount):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(bank.set_default_balance(amount))

    @commands.command(pass_context=True, no_pm=True)
    async def balance(self, ctx):
        """Gets the credit balance of the user who authors the $balance command, and returns it to the chat."""
        user = ctx.message.author
        bal = await bank.get_balance(user)

        await ctx.send("<@{}>: Your credit balance is: {}".format(user.id, bal))

    @commands.command(pass_context=True, no_pm=True)
    async def add_balance(self, ctx):
        user = ctx.message.author
        bal = await bank.get_balance(user)
        await bank.set_balance(user, bal + 1)
        await ctx.send("<@{}>: Your credit balance is: {}".format(user, bal))

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
        link = re.search("(?P<url>https?://[^\s]+)", joined_str).group("url")  # Grab only the URL.)

        canSpend = await bank.can_spend(user=user, amount=1)
        bal = await bank.get_balance(user)

        if canSpend is True:

            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            cur.execute('SELECT * FROM postbank WHERE link=?;', (link,))

            if cur.fetchone() is not None:
                await self.bot.send_message(channel, "<@{}> That link was already submitted.".format(user.id))
                conn.close()
                return

            cur.execute('INSERT INTO postbank (userid, link, numreviews, reviewers) VALUES (?,?,0,?);', (user.id,
                                                                                                         str(link),
                                                                                                         '0,1'))
            conn.commit()

            cur.execute('SELECT feedbackid FROM postbank WHERE link=?', (link,))
            rows = cur.fetchall()
            feedback_id = rows[0][0]

            conn.close()
            await ctx.send("{} submitted a track! Use `$feedback {} <feedback post here>` to give them some feedback!".format(user, feedback_id))

            await bank.withdraw_credits(user=user, amount=1)

        else:

            await self.bot.send_message(ctx.message.channel, "{}: Your post was removed because you don't have any credit. Give users $feedback to get credit.".format(user.name, bal))
            await self.bot.delete_message(ctx.message)

    @commands.command(pass_context=True, no_pm=True)
    async def feedback(self, ctx):
        user = ctx.message.author

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

                    bank.deposit_credits(user=user, amount=1)

                    conn.commit()
                    conn.close()

                else:
                    await self.bot.send_message(ctx.message.channel, "<@{}>: You already submitted a"
                                                                     " review for this ID.".format(user.id))

        else:

            await self.bot.send_message(ctx.message.channel, "<@{}>: {} is not a valid feedback ID.".format(user.id,feedback_id))
            conn.close()

        conn.close()
