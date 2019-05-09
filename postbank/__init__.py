from .postbank import PostBank


def setup(bot):
    bot.add_cog(PostBank())