import argparse
import os
import sys
from pathlib import PosixPath
from typing import Optional

from rich import print

import main as spotifetch_main
from consts import SHOULD_STOP_FILE
from fetcher import ArtistFetch, update_artist_fetch, read_pending_artist_fetches
from pack_artist_images import pack_artist_images


def main():
    parser = argparse.ArgumentParser(
        description='Spotifetch CLI - More than you asked for.'
    )
    subparsers = parser.add_subparsers(
        title='commands',
        dest='command',
        required=True,
        help='Available commands',
    )

    # Subcommand: queue
    queue = subparsers.add_parser('queue', aliases=['q'], help='Queue a spotify artist for fetching')
    queue.add_argument('urls', help='One or more URLs to the artists\' pages on Spotify', type=str, nargs='+')

    # Subcommand: edit
    edit = subparsers.add_parser('edit', aliases=['e'], help='Edit details of a queued spotify fetch')
    edit.add_argument('url_or_name', help='URL or part of the name of the artist', type=str)
    edit.add_argument('--set-name', help='Change the name of an artist', type=str)
    edit.add_argument('--ignore', help='Ignore failed tracks and continue', action='store_true')
    edit.add_argument('--clear', help='Clear the FAILED status of the fetch, allowing it to re-run',
                      action='store_true')
    edit.add_argument('--failed', help='Forcibly mark a fetch as FAILED, disallowing it to run',
                      action='store_true')
    # Subcommand: pack-images
    pack_images = subparsers.add_parser('pack-images', help='Pack all artist images into a product')

    # Subcommand: show
    show = subparsers.add_parser('show', aliases=['s', 'ls'], help='Show the status of one/all fetch(es)')
    show.add_argument('url_or_name', help='URL or part of the name of the artist', type=str, nargs='?')
    show.add_argument('--raw', action='store_true', help='Display output in raw JSON')

    # Subcommand: show-errors
    show_errors = subparsers.add_parser('show-errors', aliases=['errors', 'se'],
                                        help='Display the fetch\'s errors in the default text editor')
    show_errors.add_argument('url_or_name', help='URL or part of the name of the artist', type=str)

    # Subcommand: run
    run = subparsers.add_parser('run', help='Run the Spotifetch service in the current terminal')

    # Subcommand: stop
    stop = subparsers.add_parser('stop', help='Queue safely stopping the service once possible')

    # Subcommand: unstop
    unstop = subparsers.add_parser('unstop', help='Disable a queued stop command')

    command_parsers = {
        queue: handle_queue,
        edit: handle_edit,
        pack_images: handle_pack_images,
        show: handle_show,
        show_errors: handle_show_errors,
        run: handle_run,
        stop: handle_stop,
        unstop: handle_unstop
    }

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    command_parsers[subparsers._name_parser_map[args.command]](args)


def handle_queue(args):
    for url in args.urls:
        print(f'Queuing URL \'{url}\' to be fetched')
        update_artist_fetch(ArtistFetch(url=url))


def handle_edit(args):
    artist = find_artist_by_url_or_name(args.url_or_name, read_pending_artist_fetches())
    if not artist:
        print(f'Could not find artist identified with \'{args.url_or_name}\'')
        return

    if args.set_name:
        artist.name = args.set_name
    if args.ignore:
        artist.ignore_errors = args.ignore
    if args.clear:
        artist.status = None
    if args.failed:
        artist.status = 'FAILED'

    update_artist_fetch(artist)
    show_artist(artist)


def handle_pack_images(args):
    print('Packing artist images...')
    product_name = pack_artist_images()
    print(f'Product written to {product_name}')


def handle_show(args):
    artists = read_pending_artist_fetches()
    if args.url_or_name:
        if artist := find_artist_by_url_or_name(args.url_or_name, artists):
            artists = [artist]
        else:
            print(f'Could not find artist identified with \'{args.url_or_name}\'')
            return

    if args.raw:
        print([artist.model_dump() for artist in artists])
        return

    for idx, artist in enumerate(artists):
        print(f'{idx + 1}. ', end='')
        show_artist(artist)
        print()


def handle_show_errors(args):
    artists = read_pending_artist_fetches()
    if not (artist := find_artist_by_url_or_name(args.url_or_name, artists)):
        print(f'Could not find artist identified with \'{args.url_or_name}\'')
        return

    if not (error_log := artist.get_latest_error_file()):
        print(f"Artist '{artist.name}' does not have an error log.")
        return

    os.system(f'editor {error_log}')


def handle_run(args):
    spotifetch_main.main()


def handle_stop(args):
    SHOULD_STOP_FILE.write_text('1')
    print('Spotifetch service will stop once it\'s finished a job')


def handle_unstop(args):
    SHOULD_STOP_FILE.unlink(missing_ok=True)
    print('Cancelled stop command')


def find_artist_by_url_or_name(url_or_name: str, artists: list[ArtistFetch]) -> Optional[ArtistFetch]:
    for artist in sorted(artists, key=lambda a: a.name or ''):
        if url_or_name == artist.url or (artist.name is not None and url_or_name.lower() in artist.name.lower()):
            return artist
    return None


def show_artist(artist: ArtistFetch):
    if artist.name:
        print(f'{artist.name} ( {artist.url} )')
    else:
        print(artist.url)

    for key, value in artist.model_dump(exclude={'name', 'url'}, exclude_none=True).items():
        print(f'      {key}: {value}')


if __name__ == '__main__':
    main()
