from __future__ import annotations

import logging
import os
from argparse import ArgumentParser
from datetime import datetime
import sys
from typing import *

import aiohttp
import disnake
from disnake.ext import commands
from dotenv import load_dotenv

from config import LOGS_CHANNEL
from discotools import ChannelHandler

parser = ArgumentParser()
parser.add_argument('--local', action='store_true')
parser.add_argument('--prefix', type=str)
parser.add_argument('--log-file', action='store_true')
args = parser.parse_args()
LOCAL: bool = args.local

logger = logging.getLogger('channel_logs')
logger.level = logging.INFO

load_dotenv()
TOKEN = os.environ.get('TOKEN')

if TOKEN is None:
    raise EnvironmentError('TOKEN not found in environment variables')

# ------------------------------------------ Bot init ------------------------------------------

class HostedBot(commands.InteractionBot):
    def __init__(self, hosted: bool=False, **options: Any):
        super().__init__(**options)
        self.hosted = hosted
        self.session = aiohttp.ClientSession()
        self.run_time = datetime.now()


    async def on_slash_command_error(self, inter: disnake.ApplicationCommandInteraction, error: commands.CommandError) -> None:
        if isinstance(error, (commands.UserInputError, commands.CheckFailure)):
            if isinstance(error, commands.NotOwner):
                msg = 'You cannot use this command.'

            else:
                msg = str(error)

            await inter.send(msg, ephemeral=True)
            return

        # tell the user there was an internal error
        if isinstance(error, commands.CommandInvokeError):
            origin = error.original

            if isinstance(origin, disnake.HTTPException) and origin.code == 50035:  # Invalid Form Body
                await inter.send('Message exceeded character limit...', ephemeral=True)

            else:
                await inter.send('Command executed with an error...', ephemeral=True)

        text = (f'{error}'
                f'\nCommand: `{inter.application_command.qualified_name}`'
                f"\nArguments: {', '.join(f'`{option}`: `{value}`' for option, value in inter.filled_options.items()) or 'None'}"
                f'\nPlace: {inter.guild or inter.channel}')

        logger.exception(text, exc_info=error)


    async def on_ready(self) -> None:
        text = f'{bot.user.name} is online'
        print(text, '-' * len(text), sep='\n')


bot = HostedBot(
    hosted=LOCAL,
    intents=disnake.Intents(guilds=True),
    activity=disnake.Game('under maintenance' if LOCAL else 'SuperMechs'),
    test_guilds=[624937100034310164, 842788736008978504, 756084361450750062])

# ----------------------------------------------------------------------------------------------

handler = ChannelHandler(LOGS_CHANNEL, bot, level=logging.INFO)
logger.addHandler(handler)


class Setup(commands.Cog):
    """Module management commands for development purposes."""
    def __init__(self):
        self.last_ext = None


    @commands.slash_command(guild_ids=[624937100034310164])
    @commands.is_owner()
    async def extensions(
        self,
        inter: disnake.MessageCommandInteraction,
        action: Literal['load', 'reload', 'unload'],
        ext: str=None
    ) -> None:
        """Extension manager
        
        Parameters
        -----------
        action:
            The type of action to perform
        ext:
            The name of extension to perform action on"""
        if ext is None:
            if self.last_ext is None:
                await inter.send('No extension cached.')
                return

            ext = self.last_ext

        func: Callable[[str], None] = getattr(inter.bot, action + '_extension')

        try:
            func(ext)

        except commands.ExtensionError as e:
            print(e)
            await inter.send('An error occured', ephemeral=True)
            return

        await inter.send('Success', ephemeral=True)

        self.last_ext = ext


    @extensions.autocomplete('ext')
    async def ext_autocomp(self, inter: disnake.MessageCommandInteraction, input: str) -> list[str]:
        input = input.lower()
        return [ext for ext in inter.bot.extensions if input in ext.lower()]


    @commands.slash_command(guild_ids=[624937100034310164])
    @commands.is_owner()
    async def shutdown(self, inter: disnake.MessageCommandInteraction) -> None:
        """Terminates the bot connection."""
        await inter.send('I will be back')
        await bot.close()


class Misc(commands.Cog):
    @commands.slash_command()
    async def ping(self, inter: disnake.MessageCommandInteraction) -> None:
        """Shows bot latency"""
        await inter.response.send_message(f'Pong! {round(inter.bot.latency * 1000)}ms')


    @commands.slash_command()
    async def invite(self, inter: disnake.MessageCommandInteraction) -> None:
        """Sends an invite link for this bot to the channel"""
        await inter.send(disnake.utils.oauth_url(inter.bot.user.id, scopes=('bot', 'applications.commands')))


    @commands.slash_command(name='self')
    async def self_info(self, inter: disnake.MessageCommandInteraction) -> None:
        """Displays information about the bot."""
        app = await bot.application_info()
        invite = disnake.utils.oauth_url(bot.user.id, scopes=('bot', 'applications.commands'))
        desc = (
            f'Member of {len(bot.guilds)} server{"s" * (len(bot.guilds) != 1)}'
            f'\n**Author:** {app.owner.mention}'
            f'\n[**Invite link**]({invite})')

        uptime = datetime.now() - bot.run_time
        ss = uptime.seconds
        mm, ss = divmod(ss, 60)
        hh, mm = divmod(mm, 60)

        time_data: list[str] = []
        if uptime.days:
            time_data.append(f'{uptime.days} day{"s" * (uptime.days != 1)}')

        if hh:
            time_data.append(f'{hh} hour{"s" * (hh != 1)}')

        if mm:
            time_data.append(f'{mm} minute{"s" * (mm != 1)}')

        if ss:
            time_data.append(f'{ss} second{"s" * (ss != 1)}')

        embed = disnake.Embed(title='Bot info', description=desc, color=inter.me.color)

        tech_field = (
            f'Python build: {".".join(map(str, sys.version_info[:3]))} {sys.version_info.releaselevel}'
            f'\ndisnake version: {disnake.__version__}'
            f'\nUptime: {" ".join(time_data)}'
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name='Technical', value=tech_field)
        embed.set_footer(text='Created')
        embed.timestamp = bot.user.created_at

        await inter.send(embed=embed, ephemeral=True)



bot.add_cog(Setup())
bot.add_cog(Misc())
bot.load_extension('SM')

bot.run(TOKEN)
