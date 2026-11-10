import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
import asyncio
import logging
import os
import time
from dotenv import load_dotenv
from subsonic_client import SubsonicClient
from audio_manager import AudioManager
import wavelink
from typing import Optional

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
LAVALINK_HOST = "127.0.0.1"
LAVALINK_PORT = 2333
LAVALINK_PASSWORD = "mypassword123"

class NavidromeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        
        self.node: Optional[wavelink.Node] = None
        self.player: Optional[wavelink.Player] = None
        self.subsonic_client = None
        self.queues = {} 

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.subsonic_client = SubsonicClient(
            os.getenv("NAVIDROME_URL"),
            os.getenv("NAVIDROME_USER"),
            os.getenv("NAVIDROME_PASS"),
            self.session
        )
        
        # Подключение к Lavalink
        node = wavelink.Node(uri="http://127.0.0.1:2333", password="mypassword123")
        await wavelink.Pool.connect(nodes=[node], client=self)
        logger.info("Wavelink connected successfully.")
        
        # Синхронизация команд с Discord
        await super().setup_hook()
        synced = await self.tree.sync()
        logger.info(f"Synced {len(synced)} commands")

    async def close(self):
        if getattr(self, "session", None):
            await self.session.close()
        await super().close()

    async def on_ready(self):
        logger.info(f"Logged in as {self.user}")
        
    async def play_track_by_id(self, interaction: discord.Interaction, track_id: str, track_name: str, track_album: str = "Неизвестный альбом"):
        player = interaction.guild.voice_client
        guild_id = interaction.guild.id

        # 1. Если бот уже играет — добавляем в очередь
        if player and player.playing:
            if guild_id not in self.queues:
                self.queues[guild_id] = []
            
            stream_url = await self.subsonic_client.get_stream_url(track_id)
            if not stream_url:
                await interaction.followup.send(f"Не удалось получить поток для {track_name}.")
                return

            self.queues[guild_id].append({
                "id": track_id,
                "name": track_name,
                "album": track_album,
                "url": stream_url
            })
            await interaction.followup.send(f"Добавлено в очередь: **{track_name}**")
            return

        # 2. Если не играет — запускаем сразу
        if not player:
            channel = interaction.user.voice.channel
            player = await channel.connect(cls=wavelink.Player)
            self.player = player

        stream_url = await self.subsonic_client.get_stream_url(track_id)
        if not stream_url:
            await interaction.followup.send(f"Не удалось получить поток для {track_name}.")
            return

        try:
            search_result = await wavelink.Playable.search(stream_url)
            if search_result:
                await player.play(search_result[0])
                await interaction.followup.send(f"Now playing: **{track_name}**\nАльбом: *{track_album}*")
            else:
                await interaction.followup.send(f"Lavalink не смог распознать поток для {track_name}.")
        except Exception as e:
            logger.error(f"Error playing {track_name}: {e}")
            await interaction.followup.send(f"Ошибка при воспроизведении: {e}")
       
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        # Когда трек заканчивается, проверяем очередь
        player = payload.player
        if not player:
            return
            
        guild_id = player.guild.id
        queue = self.queues.get(guild_id, [])
        
        # Если очередь пуста — ничего не делаем
        if not queue:
            return
            
        # Берем следующий трек
        next_track = queue.pop(0)
        stream_url = next_track["url"]
        
        try:
            search_result = await wavelink.Playable.search(stream_url)
            if search_result:
                await player.play(search_result[0])
                # Отправляем сообщение в тот же канал, где сидит бот
                if player.channel:
                    await player.channel.send(f"Now playing: **{next_track['name']}**\nАльбом: *{next_track['album']}*")
        except Exception as e:
            logger.error(f"Error playing next track: {e}")

class SelectTrackView(discord.ui.View):
    def __init__(self, tracks: list, bot_instance):
        super().__init__(timeout=60)
        self.tracks = tracks
        self.bot = bot_instance

    async def handle_selection(self, interaction: discord.Interaction, index: int):
        if index < 0 or index >= len(self.tracks):
            await interaction.response.send_message("Ошибка выбора.", ephemeral=True)
            return

        track = self.tracks[index]
        track_id = track.get("id")
        track_name = track.get("title")
        track_album = track.get("album", "Неизвестный альбом")

        if not track_id:
            await interaction.response.send_message("Ошибка: У выбранного трека нет ID.", ephemeral=True)
            return

        await self.bot.play_track_by_id(interaction, track_id, track_name, track_album)
        await interaction.message.delete()

    @discord.ui.button(label="1", style=discord.ButtonStyle.primary)
    async def button1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, 0)

    @discord.ui.button(label="2", style=discord.ButtonStyle.primary)
    async def button2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, 1)

    @discord.ui.button(label="3", style=discord.ButtonStyle.primary)
    async def button3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, 2)

    @discord.ui.button(label="4", style=discord.ButtonStyle.primary)
    async def button4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, 3)

    @discord.ui.button(label="5", style=discord.ButtonStyle.primary)
    async def button5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_selection(interaction, 4)

bot = NavidromeBot()


@bot.tree.command(name="play", description="Play a track from Navidrome via Lavalink")
@app_commands.describe(song_name="The name of the song to play")
async def play(interaction: discord.Interaction, song_name: str):
    await interaction.response.defer()
    logger.info(f"Received play command for: {song_name}")
    
    if not interaction.user.voice:
        await interaction.followup.send("You need to be in a voice channel to play music.")
        return

    # 1. Поиск трека в Navidrome
    tracks = await bot.subsonic_client.search_track(song_name)
    
    if not tracks:
        await interaction.followup.send(f"No tracks found in Navidrome for '{song_name}'.")
        return

    # 2. Выбор первого трека
    track = tracks[0]
    track_id = track.get("id")
    track_name = track.get("title")
    track_album = track.get("album", "Неизвестный альбом")

    if not track_id:
        await interaction.followup.send("Не удалось получить ID трека из ответа Navidrome")
        return

    # 3. Получение прямого URL потока
    stream_url = await bot.subsonic_client.get_stream_url(track_id)
    
    if not stream_url:
        await interaction.followup.send(f"Could not retrieve stream URL for {track_name}.")
        return

    # 4. Подключение к каналу через Wavelink Player
    channel = interaction.user.voice.channel
    player = interaction.guild.voice_client
    
    # Если плеер уже есть в другом канале, отключаем его
    if player and player.channel != channel:
        await player.disconnect()
        player = None
        
    # Если плеера нет, создаем
    if not player:
        player = await channel.connect(cls=wavelink.Player)

    # 5. Поиск трека в Lavalink по прямому URL
    search_result = await wavelink.Playable.search(stream_url)
    
    if not search_result:
        await interaction.followup.send(f"Lavalink не смог распознать поток для {track_name}.")
        return

    # 6. Воспроизведение
    await player.play(search_result[0])
    await interaction.followup.send(f"Now playing: **{track_name}**")


@bot.tree.command(name="stop", description="Disconnect the bot from the voice channel")
async def stop(interaction: discord.Interaction):
    await interaction.response.defer()
    if not interaction.user.voice:
        await interaction.followup.send("Вы должны быть в голосовом канале.")
        return

    player = interaction.guild.voice_client
    if player is None:
        await interaction.followup.send("Бот не подключён к каналу.")
        return

    await player.disconnect()
    await interaction.followup.send("Бот отключён.")


@bot.tree.command(name="pause", description="Pause the current track")
async def pause(interaction: discord.Interaction):
    await interaction.response.defer()
    if not interaction.user.voice:
        await interaction.followup.send("Вы должны быть в голосовом канале.")
        return

    player = interaction.guild.voice_client
    if player is None:
        await interaction.followup.send("Бот не подключён к каналу.")
        return

    if player.paused:
        await interaction.followup.send("Уже на паузе.")
    else:
        await player.pause(True)
        await interaction.followup.send("Пауза.")


@bot.tree.command(name="resume", description="Resume the current track")
async def resume(interaction: discord.Interaction):
    await interaction.response.defer()
    if not interaction.user.voice:
        await interaction.followup.send("Вы должны быть в голосовом канале.")
        return

    player = interaction.guild.voice_client
    if player is None:
        await interaction.followup.send("Бот не подключён к каналу.")
        return

    if not player.paused:
        await interaction.followup.send("Не на паузе.")
    else:
        await player.pause(False)
        await interaction.followup.send("Продолжаю.")

@bot.tree.command(name="search", description="Search for a track and select it from the list")
@app_commands.describe(query="The name of the song to search for")
async def search(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    logger.info(f"Received search command for: {query}")
    
    tracks = await bot.subsonic_client.search_track(query)
    
    if not tracks:
        await interaction.followup.send(f"Ничего не найдено по запросу '{query}'.")
        return

    results = tracks[:5]
    
    embed = discord.Embed(title=f"Search results for: {query}", description="Choose a track to play:")
    description = ""
    for i, track in enumerate(results, 1):
        title = track.get('title', 'Unknown')
        artist = track.get('artist', 'Unknown')
        album = track.get('album', 'Unknown Album')
        
        description += f"{i}. **{title}** - {artist}\n   *Альбом: {album}*\n"
    
    embed.description = description
    
    view = SelectTrackView(results, bot)
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="skip", description="Skip the current track")
async def skip(interaction: discord.Interaction):
    await interaction.response.defer()
    
    if not interaction.user.voice:
        await interaction.followup.send("Вы должны быть в голосовом канале.")
        return

    player = interaction.guild.voice_client
    if player is None:
        await interaction.followup.send("Бот не подключён к каналу.")
        return

    if not player.playing:
        await interaction.followup.send("Сейчас ничего не играет.")
        return
    # Останавливаем текущий трек. 
    # Это вызовет событие on_wavelink_track_end, и бот подхватит следующий из очереди.
    await player.stop()
    await interaction.followup.send("Трек пропущен.")
    
@bot.tree.command(name="queue", description="Show the current track queue")
async def queue(interaction: discord.Interaction):
    await interaction.response.defer()
    
    if not interaction.guild:
        await interaction.followup.send("Эта команда работает только на сервере.")
        return

    guild_id = interaction.guild.id
    queue = bot.queues.get(guild_id, [])

    if not queue:
        await interaction.followup.send("Очередь пуста. Добавьте треки через `/play` или `/search`.")
        return

    # Формируем Embed
    embed = discord.Embed(
        title="Очередь треков",
        description="Следующие треки в очереди:",
        color=discord.Color.blue()
    )

    # Показываем первые 10 треков, чтобы не превысить лимит Discord
    for i, track in enumerate(queue[:10], 1):
        name = track.get("name", "Неизвестно")
        album = track.get("album", "Неизвестный альбом")
        embed.add_field(
            name=f"{i}. {name}",
            value=f"Альбом: *{album}*",
            inline=False
        )

    # Если треков больше 10, добавляем приписку
    if len(queue) > 10:
        embed.set_footer(text=f"... и еще {len(queue) - 10} треков")
    else:
        embed.set_footer(text=f"Всего треков в очереди: {len(queue)}")

    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    # Check if Opus is loaded
    if not discord.opus.is_loaded():
        print("Warning: Opus not loaded automatically. Check system setup.")
    
    bot.run(TOKEN)