# -*- coding: utf-8 -*-
import discord
import collections
import asyncio
import re
from discord.ext import commands

# This cog is a fork of ReactPoll by FlapJack.
# The original ReactPoll did not support more than 9 options.
# This reaction based poll will support the maximum allowed reacts by discord.
# Fork by BraveLittleRoaster to include the full amount of reacts so polls of all available sizes are supported.

class AlphaPoll:

	"""Create polls using emoji reactions"""

	def __init__(self, bot):
		self.bot = bot
		self.poll_sessions = []

	@commands.command(pass_context=True, no_pm=True)
	async def multipoll(self, ctx, *text):
		"""Starts/stops a reaction poll
		Usage example (time  and  multiple choice arguments are optional)
		multipoll Is this a poll?;Yes;No;Maybe;n=1;t=60
		multipoll stop"""
		message = ctx.message
		channel = message.channel
		server = message.server
		if len(text) == 1:
			if text[0].lower() == "stop":
				await self.endpoll(message)
				return
		if not self.getPollByChannel(message):
			check = " ".join(text).lower()
			if "@everyone" in check or "@here" in check:
				await self.bot.say("Nice try.")
				return
			if not channel.permissions_for(server.me).manage_messages:
				await self.bot.say("I require the 'Manage Messages' "
								   "permission in this channel to conduct "
								   "a reaction poll.")
				return
			p = NewReactPoll(message, " ".join(text), self)
			if p.valid:
				if p.mc_valid:
					self.poll_sessions.append(p)
					await p.start()
				else:
					await self.bot.say("`Number of votes per person is greater than number of options`")
			else:
				await self.bot.say("`[p]multipoll question;option1;option2...;n=1;t=60`")
		else:
			await self.bot.say("A reaction poll is already ongoing in this channel.")

	async def endpoll(self, message):
		if self.getPollByChannel(message):
			p = self.getPollByChannel(message)
			if p.author == message.author.id:  # or isMemberAdmin(message)
				await self.getPollByChannel(message).endPoll()
			else:
				await self.bot.say("Only admins and the author can stop the poll.")
		else:
			await self.bot.say("There's no reaction poll ongoing in this channel.")

	def getPollByChannel(self, message):
		for poll in self.poll_sessions:
			if poll.channel == message.channel:
				return poll
		return False

	async def check_poll_votes(self, message):
		if message.author.id != self.bot.user.id:
			if self.getPollByChannel(message):
					self.getPollByChannel(message).checkAnswer(message)

	async def reaction_listener(self, reaction, user):
		# Listener is required to remove bad reactions
		if user == self.bot.user:
			return  # Don't remove bot's own reactions
		message = reaction.message
		emoji = reaction.emoji
		if self.getPollByChannel(message):
			p = self.getPollByChannel(message)
			if message.id == p.message.id and not reaction.custom_emoji and emoji in p.emojis:
				# Valid reaction
				if user.id not in p.already_voted:
					# First vote
					p.already_voted[user.id] = set()
					p.already_voted[user.id].add(str(emoji))
					
					return
				else:
					if len(p.already_voted[user.id])<p.mc:
						p.already_voted[user.id].add(str(emoji))
						
						return
					# Allow subsequent vote but remove the previous
					else:
						await self.bot.remove_reaction(message, p.already_voted[user.id].pop(), user)
						p.already_voted[user.id].add(str(emoji))
					   
						return

	def __unload(self):
		for poll in self.poll_sessions:
			if poll.wait_task is not None:
				poll.wait_task.cancel()
	@commands.command(pass_context=True, no_pm=True)
	async def apoll(self, ctx, *text):
		"""Starts/stops a reaction poll
		Usage example (time argument is optional)
		apoll Is this a poll?;Yes;No;Maybe;t=60
		apoll stop"""
		message = ctx.message
		channel = message.channel
		server = message.server
		if len(text) == 1:
			if text[0].lower() == "stop":
				await self.endpoll(message)
				return
		if not self.getPollByChannel(message):
			check = " ".join(text).lower()
			if "@everyone" in check or "@here" in check:
				await self.bot.say("Nice try.")
				return
			if not channel.permissions_for(server.me).manage_messages:
				await self.bot.say("I require the 'Manage Messages' "
								   "permission in this channel to conduct "
								   "a reaction poll.")
				return
			p = NewReactPoll(message, " ".join(text), self)
			if p.valid:
				self.poll_sessions.append(p)
				await p.start()
			else:
				await self.bot.say("`[p]apoll question;option1;option2...;t=60`")
		else:
			await self.bot.say("A reaction poll is already ongoing in this channel.")

class NewReactPoll():
	# This can be made a subclass of NewPoll()

	def __init__(self, message, text, main):
		self.channel = message.channel
		self.author = message.author.id
		self.client = main.bot
		self.poll_sessions = main.poll_sessions
		self.duration = 60  # Default duration
		self.mc = 1
		self.wait_task = None

		# Build a dict of alphanumeric mappings to unicode. Discord is really picky about these.
		# Sending the raw unicode for keycap 1-9 did not work.
		self.num_emojis = collections.OrderedDict([
			('1', '1⃣'),
			('2', '2⃣'),
			('3', '3⃣'),
			('4', '4⃣'),
			('5', '5⃣'),
			('6', '6⃣'),
			('7', '7⃣'),
			('8', '8⃣'),
			('9', '9⃣'),
			('10', u'\U0001F51F'),
			('a', '\N{REGIONAL INDICATOR SYMBOL LETTER A}'), ('b', '\N{REGIONAL INDICATOR SYMBOL LETTER B}'),
			('c', '\N{REGIONAL INDICATOR SYMBOL LETTER C}'),
			('d', '\N{REGIONAL INDICATOR SYMBOL LETTER D}'), ('e', '\N{REGIONAL INDICATOR SYMBOL LETTER E}'),
			('f', '\N{REGIONAL INDICATOR SYMBOL LETTER F}'),
			('g', '\N{REGIONAL INDICATOR SYMBOL LETTER G}'), ('h', '\N{REGIONAL INDICATOR SYMBOL LETTER H}'),
			('i', '\N{REGIONAL INDICATOR SYMBOL LETTER I}'),
			('j', '\N{REGIONAL INDICATOR SYMBOL LETTER J}'), ('k', '\N{REGIONAL INDICATOR SYMBOL LETTER K}'),
			('l', '\N{REGIONAL INDICATOR SYMBOL LETTER L}'),
			('m', '\N{REGIONAL INDICATOR SYMBOL LETTER M}'), ('n', '\N{REGIONAL INDICATOR SYMBOL LETTER N}'),
			('o', '\N{REGIONAL INDICATOR SYMBOL LETTER O}'),
			('p', '\N{REGIONAL INDICATOR SYMBOL LETTER P}'), ('q', '\N{REGIONAL INDICATOR SYMBOL LETTER Q}'),
			('r', '\N{REGIONAL INDICATOR SYMBOL LETTER R}'),
			('s', '\N{REGIONAL INDICATOR SYMBOL LETTER S}'), ('t', '\N{REGIONAL INDICATOR SYMBOL LETTER T}'),
			('u', '\N{REGIONAL INDICATOR SYMBOL LETTER U}'),
			('v', '\N{REGIONAL INDICATOR SYMBOL LETTER V}'), ('w', '\N{REGIONAL INDICATOR SYMBOL LETTER W}'),
			('x', '\N{REGIONAL INDICATOR SYMBOL LETTER X}'),
			('y', '\N{REGIONAL INDICATOR SYMBOL LETTER Y}'), ('z', '\N{REGIONAL INDICATOR SYMBOL LETTER Z}'),
			('0', '0⃣')])
		# Build a dict of alphanumeric mappings to unicode

		# Build the alphanum dict into an array to iterate over this easier.
		self.alphanum_array_key = list(self.num_emojis.keys())
		
		self.alphanum_array_val = list(self.num_emojis.values())
		

		#print(self.alphanum_array_key)
		msg = [ans.strip() for ans in text.split(";")]
		#print(msg)
		for x in range(0,len(msg)-1):
					if not msg[x]:
						msg.remove(msg[x])

		# Detect optional duration parameter
		tn= -1
		for x in range(0,len(msg)):
			if "t=" in msg[x]:
				tn = x

		nn = -1
		for x in range(0,len(msg)):
			if "n=" in msg[x]:
				nn = x


		if tn>=0:
			dur = msg[tn].strip().split("t=")[1]
			if re.match(r'[0-9]{1,18}$', dur):
				self.duration = int(dur)
			else:
				self.duration = 60
			msg.remove(msg[tn])

		if tn>=nn:
			nn = nn
		else:
			if tn>0: 
				nn=nn-1

		if nn>=0:
			dur = msg[nn].strip().split("n=")[1]
			if re.match(r'[0-9]{1,18}$', dur):
				self.mc = int(dur)
			else:
				self.mc = 1
			msg.remove(msg[nn])
		# Reaction polling supports maximum of 20 answers (discord hard limit) and minimum of 2. ctx counts as 1 arg.
		if len(msg) < 2 or len(msg) > 21:
			print("Options Exceed available reaction limits: %s arguments, %s emojis" % (len(msg),
																						 len(self.alphanum_array_key)))
			self.valid = False
			return None
		else:
			self.valid = True
		if self.mc > len(msg):
			self.mc_valid = False
			return None
		else:
			self.mc_valid = True
			
		self.already_voted = {}
		self.question = msg[0]
		msg.remove(self.question)
		self.answers = {}  # Made this a dict to make my life easier for now
		self.emojis = []
		self.em_sort = []
		i = 0
		for answer in msg:  # {emoji: {answer, votes}}
			"""old format by FlapJack was {id: {answer, votes}, broke async due to the id key value being maped to
			the unicode for keycap 1-9.  
			New format is like {emoji: {answer: votes}}"""
			self.emojis.append(self.alphanum_array_val[i])
			self.em_sort.append(self.alphanum_array_val[i])
			answer = self.emojis[i] + ' ' + answer
			self.answers[self.alphanum_array_val[i]] = {"ANSWER": answer, "VOTES": 0}
			i += 1
		
		self.answers = collections.OrderedDict(sorted(self.answers.items(), key=lambda pair: self.em_sort.index(pair[0])))
		self.message = None

	async def poll_wait(self):
		# print("Sleeping for %s" % self.duration)
		await asyncio.sleep(self.duration)
		if self.valid:
			# print("Expiring poll")
			await self.endPoll(expired=True)

	# Override NewPoll methods for starting and stopping polls
	async def start(self):
		msg = "**POLL STARTED!**\n\n{}\n\n".format(self.question)
		for id, data in self.answers.items():
			# msg += "{}\n".format(data["ANSWER"])
			msg += "{}\n".format(data["ANSWER"])
		if self.mc  == 1:
			msg += ("\nSelect a react to vote!")
		else:
			msg += ("\nSelect "+str(self.mc)+" reacts to vote!")
		msg += ("\nPoll closes in {} seconds.".format(self.duration))
		self.message = await self.client.send_message(self.channel, msg)
		for emoji in self.emojis:
			await self.client.add_reaction(self.message, emoji)
			await asyncio.sleep(0.2)

		self.wait_task = self.client.loop.create_task(self.poll_wait())

	async def endPoll(self, expired=False):
		# print("Attempting to end poll")
		self.valid = False
		if not expired:
			# print("Not expired yet")
			self.wait_task.cancel()
		# Need a fresh message object
		# print("Getting fresh message obj")
		self.message = await self.client.get_message(self.channel, self.message.id)
		msg = "**POLL ENDED!**\n\n{}\n\n".format(self.question)
		for reaction in self.message.reactions:
			if reaction.emoji in self.emojis:
				# print("Found valid emoji %s. Count: %s" % (reaction.emoji, reaction.count))
				self.answers[reaction.emoji]["VOTES"] = reaction.count - 1
		# print("Clearing reactions")
		await self.client.clear_reactions(self.message)
		cur_max = 0 # Track the winning number of votes
		# Double iteration probably not the fastest way, but works for now
		for data in self.answers.values():
			if data["VOTES"] > cur_max:
				cur_max = data["VOTES"]
		for data in self.answers.values():
			if cur_max > 0 and data["VOTES"] == cur_max:
				msg += "**{} - {} votes**\n".format(data["ANSWER"], str(data["VOTES"]))
			else:
				msg += "*{}* - {} votes\n".format(data["ANSWER"], str(data["VOTES"]))

		await self.client.send_message(self.channel, msg)
		self.poll_sessions.remove(self)


def setup(bot):
	n = AlphaPoll(bot)
	bot.add_cog(n)
	bot.add_listener(n.reaction_listener, "on_reaction_add")