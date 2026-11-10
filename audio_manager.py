import discord
from discord.ext import commands
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class AudioManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def after_playing(self, error):
        if error:
            logger.error(f"Player error: {error}")
        else:
            logger.info("Playback finished.")

    async def play_audio(self, ctx: commands.Interaction, voice_channel: discord.VoiceChannel, stream_url: str):
        # Check if bot is in a voice channel
        voice_client = ctx.guild.voice_client
        
        # If bot is not in a voice channel, connect to the one from the context
        if voice_client is None:
            await voice_channel.connect()
            voice_client = ctx.guild.voice_client

        # If connected to a different channel, disconnect and reconnect
        if voice_client.channel != voice_channel:
            await voice_client.disconnect()
            await voice_channel.connect()
            voice_client = ctx.guild.voice_client

        # Stop existing playback if any
        if voice_client.is_playing():
            voice_client.stop()

        # Create and play the source using PCMAudio
        source = discord.FFmpegPCMAudio(stream_url, options='-vn -ar 48000 -ac 2')
        
        voice_client.play(source, after=self.after_playing)
        logger.info(f"Started playing: {stream_url}")
        
        logger.info(f"Voice client playing: {voice_client.is_playing()}")
        logger.info(f"Source format: {source.__class__.__name__}")
# Если есть доступ к соединению:
        logger.info(f"DAVE session: {voice_client._connection.dave_session}")

    async def stop_audio(self, ctx: commands.Interaction):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.disconnect()
