import colorsys
import logging
import pprint
import textwrap
import typing
from collections import Mapping
from typing import Any, Optional

import discord
from discord import CategoryChannel, Colour, Embed, Member, TextChannel, VoiceChannel
from discord import Role, utils
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context, command, group

from bot.constants import Channels, Emojis, MODERATION_ROLES, STAFF_ROLES
from bot.decorators import InChannelCheckFailure, with_role, in_channel
from bot.utils.checks import with_role_check
from bot.utils.time import time_since

log = logging.getLogger(__name__)


class Information(Cog):
    """A cog with commands for generating embeds with server info, such as server stats and user info."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @with_role(*MODERATION_ROLES)
    @command(name="roles")
    async def roles_info(self, ctx: Context) -> None:
        """Returns a list of all roles and their corresponding IDs."""
        # Sort the roles alphabetically and remove the @everyone role
        roles = sorted(ctx.guild.roles, key=lambda role: role.name)
        roles = [role for role in roles if role.name != "@everyone"]

        # Build a string
        role_string = ""
        for role in roles:
            role_string += f"`{role.id}` - {role.mention}\n"

        # Build an embed
        embed = Embed(
            title="Role information",
            colour=Colour.blurple(),
            description=role_string
        )

        embed.set_footer(text=f"Total roles: {len(roles)}")

        await ctx.send(embed=embed)

    @with_role(*MODERATION_ROLES)
    @command(name="role")
    async def role_info(self, ctx: Context, *roles: typing.Union[Role, str]) -> None:
        """
        Return information on a role or list of roles.

        To specify multiple roles just add to the arguments, delimit roles with spaces in them using quotation marks.
        """
        parsed_roles = []

        for role_name in roles:
            if isinstance(role_name, Role):
                # Role conversion has already succeeded
                parsed_roles.append(role_name)
                continue

            role = utils.find(lambda r: r.name.lower() == role_name.lower(), ctx.guild.roles)

            if not role:
                await ctx.send(f":x: Could not convert `{role_name}` to a role")
                continue

            parsed_roles.append(role)

        for role in parsed_roles:
            embed = Embed(
                title=f"{role.name} info",
                colour=role.colour,
            )

            embed.add_field(name="ID", value=role.id, inline=True)

            embed.add_field(name="Colour (RGB)", value=f"#{role.colour.value:0>6x}", inline=True)

            h, s, v = colorsys.rgb_to_hsv(*role.colour.to_rgb())

            embed.add_field(name="Colour (HSV)", value=f"{h:.2f} {s:.2f} {v}", inline=True)

            embed.add_field(name="Member count", value=len(role.members), inline=True)

            embed.add_field(name="Position", value=role.position)

            embed.add_field(name="Permission code", value=role.permissions.value, inline=True)

            await ctx.send(embed=embed)

    @command(name="server", aliases=["server_info", "guild", "guild_info"])
    async def server_info(self, ctx: Context) -> None:
        """Returns an embed full of server information."""
        created = time_since(ctx.guild.created_at, precision="days")
        features = ", ".join(ctx.guild.features)
        region = ctx.guild.region

        # How many of each type of channel?
        roles = len(ctx.guild.roles)
        channels = ctx.guild.channels
        text_channels = 0
        category_channels = 0
        voice_channels = 0
        for channel in channels:
            if type(channel) == TextChannel:
                text_channels += 1
            elif type(channel) == CategoryChannel:
                category_channels += 1
            elif type(channel) == VoiceChannel:
                voice_channels += 1

        # How many of each user status?
        member_count = ctx.guild.member_count
        members = ctx.guild.members
        online = 0
        dnd = 0
        idle = 0
        offline = 0
        for member in members:
            if str(member.status) == "online":
                online += 1
            elif str(member.status) == "offline":
                offline += 1
            elif str(member.status) == "idle":
                idle += 1
            elif str(member.status) == "dnd":
                dnd += 1

        embed = Embed(
            colour=Colour.blurple(),
            description=textwrap.dedent(f"""
                **Server information**
                Created: {created}
                Voice region: {region}
                Features: {features}

                **Counts**
                Members: {member_count:,}
                Roles: {roles}
                Text: {text_channels}
                Voice: {voice_channels}
                Channel categories: {category_channels}

                **Members**
                {Emojis.status_online} {online}
                {Emojis.status_idle} {idle}
                {Emojis.status_dnd} {dnd}
                {Emojis.status_offline} {offline}
            """)
        )

        embed.set_thumbnail(url=ctx.guild.icon_url)

        await ctx.send(embed=embed)

    @command(name="user", aliases=["user_info", "member", "member_info"])
    async def user_info(self, ctx: Context, user: Member = None, hidden: bool = False) -> None:
        """Returns info about a user."""
        if user is None:
            user = ctx.author

        # Do a role check if this is being executed on someone other than the caller
        if user != ctx.author and not with_role_check(ctx, *MODERATION_ROLES):
            await ctx.send("You may not use this command on users other than yourself.")
            return

        # Non-moderators may only do this in #bot-commands and can't see hidden infractions.
        if not with_role_check(ctx, *STAFF_ROLES):
            if not ctx.channel.id == Channels.bot:
                raise InChannelCheckFailure(Channels.bot)
            # Hide hidden infractions for users without a moderation role
            hidden = False

        # User information
        created = time_since(user.created_at, max_units=3)

        name = str(user)
        if user.nick:
            name = f"{user.nick} ({name})"

        # Member information
        joined = time_since(user.joined_at, precision="days")

        # You're welcome, Volcyyyyyyyyyyyyyyyy
        roles = ", ".join(role.mention for role in user.roles if role.name != "@everyone")

        # Infractions
        infractions = await self.bot.api_client.get(
            'bot/infractions',
            params={
                'hidden': str(hidden),
                'user__id': str(user.id)
            }
        )

        infr_total = 0
        infr_active = 0

        # At least it's readable.
        for infr in infractions:
            if infr["active"]:
                infr_active += 1

            infr_total += 1

        # Let's build the embed now
        embed = Embed(
            title=name,
            description=textwrap.dedent(f"""
                **User Information**
                Created: {created}
                Profile: {user.mention}
                ID: {user.id}

                **Member Information**
                Joined: {joined}
                Roles: {roles or None}

                **Infractions**
                Total: {infr_total}
                Active: {infr_active}
            """)
        )

        embed.set_thumbnail(url=user.avatar_url_as(format="png"))
        embed.colour = user.top_role.colour if roles else Colour.blurple()

        await ctx.send(embed=embed)

    def format_fields(self, mapping: Mapping[str, Any], field_width: Optional[int] = None):
        # sorting is technically superfluous but nice if you want to look for a specific field
        fields = sorted(mapping.items(), key=lambda item: item[0])

        if field_width is None:
            field_width = len(max(mapping.keys(), key=len))

        out = ''

        for key, val in fields:
            if isinstance(val, dict):
                # if we have dicts inside dicts we want to apply the same treatment to the inner dictionaries
                inner_width = int(field_width * 1.6)
                val = '\n' + self.format_fields(val, field_width=inner_width)

            elif isinstance(val, str):
                # split up text since it might be long
                text = textwrap.fill(val, width=100, replace_whitespace=False)

                # indent it, I guess you could do this with `wrap` and `join` but this is nicer
                val = textwrap.indent(text, ' ' * (field_width + len(': ')))

                # the first line is already indented so we `str.lstrip` it
                val = val.lstrip()

            if key == 'color':
                # makes the base 10 representation of a hex number readable to humans
                val = hex(val)

            out += '{0:>{width}}: {1}\n'.format(key, val, width=field_width)

        # remove trailing whitespace
        return out.rstrip()

    @group(invoke_without_command=True)
    @in_channel(Channels.bot, bypass_roles=STAFF_ROLES)
    async def raw(self, ctx: Context, *, message: discord.Message, json: bool = False):
        """Shows information about the raw API response."""

        # I *guess* it could be deleted right as the command is invoked but I felt like it wasn't worth handling
        # doing this extra request is also much easier than trying to convert everything back into a dictionary again
        raw_data = await ctx.bot.http.get_message(message.channel.id, message.id)

        paginator = commands.Paginator()

        def add_content(title, content):
            paginator.add_line(f'== {title} ==\n')
            # replace backticks as it breaks out of code blocks. Spaces seemed to be the most reasonable solution.
            # we hope it's not close to 2000
            paginator.add_line(content.replace('```', '`` `'))
            paginator.close_page()

        if message.content:
            add_content('Raw message', message.content)

        transformer = pprint.pformat if json else self.format_fields
        for field_name in 'embeds attachments'.split():
            data = raw_data[field_name]

            if not data:
                continue

            total = len(data)
            for current, item in enumerate(data, start=1):
                title = f'Raw {field_name} ({current}/{total})'
                add_content(title, transformer(item))

        for page in paginator.pages:
            await ctx.send(page)

    @raw.command()
    async def json(self, ctx: Context, message: discord.Message):
        await ctx.invoke(self.raw, message=message, json=True)


def setup(bot: Bot) -> None:
    """Information cog load."""
    bot.add_cog(Information(bot))
    log.info("Cog loaded: Information")
