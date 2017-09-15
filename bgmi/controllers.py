# coding=utf-8
from __future__ import print_function, unicode_literals

import time

from bgmi.config import write_config, SUPPORT_WEBSITE
from bgmi.constants import *
from bgmi.download import download_prepare
from bgmi.download import get_download_class
from bgmi.fetch import website
from bgmi.models import (Bangumi, Followed, Download, Filter, Subtitle, STATUS_FOLLOWED, STATUS_UPDATED,
                         STATUS_NORMAL, STATUS_NOT_DOWNLOAD, DB)
from bgmi.script import ScriptRunner
from bgmi.utils import print_warning, print_info, print_success, print_error


def add(ret):
    """
    ret.name :list[str]
    """
    # action add
    # add bangumi by a list of bangumi name
    result = {}
    if not Bangumi.get_all_bangumi():
        print_warning('No bangumi data in database, fetching...')
        website.fetch(save=True, group_by_weekday=False)

    for bangumi in ret.name:
        bangumi_obj = Bangumi(name=bangumi)
        data = bangumi_obj.select(one=True, fields=['id', 'name', 'keyword'])
        if data:
            followed_obj = Followed(bangumi_name=data['name'], status=STATUS_FOLLOWED)
            followed_obj.select_obj()
            if not followed_obj or followed_obj.status == STATUS_NORMAL:
                if not followed_obj:
                    bangumi_data, _ = website.get_maximum_episode(bangumi_obj, subtitle=False, max_page=1)
                    followed_obj.episode = bangumi_data['episode'] if ret.episode is None else getattr(ret,
                                                                                                       'episode', None)
                    followed_obj.save()
                else:
                    followed_obj.status = STATUS_FOLLOWED
                    followed_obj.save()
                print_success('{0} has been followed'.format(bangumi_obj))
                result[bangumi] = {'status': 'success'}
            else:
                print_warning('{0} already followed'.format(bangumi_obj))
                result[bangumi] = {'status': 'warning', 'message': '{0} already followed'.format(bangumi_obj)}
        else:
            print_error('{0} not found, please check the name'.format(bangumi))
            result[bangumi] = {'status': 'error', 'message': '{0} not found, please check the name'.format(bangumi)}
    return result


def print_filter(followed_filter_obj):
    print_info('Followed subtitle group: {0}'.format(', '.join(map(lambda s: s['name'],
                                                                   Subtitle.get_subtitle(
                                                                       followed_filter_obj.subtitle.split(', '))))
                                                     if followed_filter_obj.subtitle else 'None'))
    print_info('Include keywords: {0}'.format(followed_filter_obj.include))
    print_info('Exclude keywords: {0}'.format(followed_filter_obj.exclude))
    print_info('Regular expression: {0}'.format(followed_filter_obj.regex))


def filter_(ret):
    bangumi_obj = Bangumi(name=ret.name)
    bangumi_obj.select_obj()
    if not bangumi_obj:
        print_error('Bangumi {0} does not exist.'.format(bangumi_obj.name))

    followed_obj = Followed(bangumi_name=bangumi_obj.name)
    followed_obj.select_obj()

    if not followed_obj:
        print_error('Bangumi {0} has not subscribed, try \'bgmi add "{1}"\'.'.format(bangumi_obj.name,
                                                                                     bangumi_obj.name))

    subtitle = ret.subtitle
    include = ret.include
    exclude = ret.exclude
    regex = ret.regex

    followed_filter_obj = Filter(bangumi_name=ret.name)
    followed_filter_obj.select_obj()

    if not followed_filter_obj:
        followed_filter_obj.save()

    if subtitle is not None:
        subtitle = map(lambda s: s.strip(), subtitle.split(','))

        subtitle = map(lambda s: s['id'], Subtitle.get_subtitle_by_name(subtitle))

        subtitle_list = [s.split('.')[0] for s in bangumi_obj.subtitle_group.split(', ')
                         if '.' in s]
        subtitle_list.extend(bangumi_obj.subtitle_group.split(', '))
        subtitle = filter(lambda s: True if s in subtitle_list else False, subtitle)
        subtitle = ', '.join(subtitle)
        followed_filter_obj.subtitle = subtitle

    if include is not None:
        followed_filter_obj.include = include

    if exclude is not None:
        followed_filter_obj.exclude = exclude

    if regex is not None:
        followed_filter_obj.regex = regex

    followed_filter_obj.save()
    print_info('Usable subtitle group: {0}'.format(', '.join(map(lambda s: s['name'],
                                                                 Subtitle.get_subtitle(
                                                                     bangumi_obj.subtitle_group.split(', ')))))
               if bangumi_obj.subtitle_group else 'None')

    print_filter(followed_filter_obj)


def delete(ret):
    """
    ret.clear_all:ool
    or
    ret.name:str
    :param ret:
    :return:
    """
    # action delete
    # just delete subscribed bangumi or clear all the subscribed bangumi
    result = {}
    if ret.clear_all:
        if Followed.delete_followed(batch=ret.batch):
            print_success('all subscriptions have been deleted')
            result['clear_all'] = {'status': "success"}
        else:
            print_error('user canceled')
    elif ret.name:
        for name in ret.name:
            followed = Followed(bangumi_name=name)
            if followed.select():
                followed.delete()
                print_warning('Bangumi {} has been deleted'.format(name))
                result[name] = {'status': 'warning', 'message': 'Bangumi {} has been deleted'.format(name)}
            else:
                print_error('Bangumi %s does not exist' % name, exit_=False)
    else:
        print_warning('Nothing has been done.')
        result = {'status': 'error', 'message': 'Nothing has been done.'}
    return result


def update(ret):
    ignore = not bool(ret.not_ignore)
    print_info('marking bangumi status ...')
    now = int(time.time())
    for i in Followed.get_all_followed():
        if i['updated_time'] and int(i['updated_time'] + 86400) < now:
            followed_obj = Followed(bangumi_name=i['bangumi_name'])
            followed_obj.status = STATUS_FOLLOWED
            followed_obj.save()

    for script in ScriptRunner().scripts:
        obj = script.Model().obj
        if obj['updated_time'] and int(obj['updated_time'] + 86400) < now:
            obj.status = STATUS_FOLLOWED
            obj.save()

    print_info('updating bangumi data ...')
    website.fetch(save=True, group_by_weekday=False)
    print_info('updating subscriptions ...')
    download_queue = []

    if ret.download:
        if not ret.name:
            print_warning('No specified bangumi, ignore `--download` option')
        if len(ret.name) > 1:
            print_warning('Multiple specified bangumi, ignore `--download` option')

    if not ret.name:
        updated_bangumi_obj = Followed.get_all_followed()
    else:
        updated_bangumi_obj = []
        for i in ret.name:
            f = Followed(bangumi_name=i)
            f.select_obj()
            updated_bangumi_obj.append(f)

    runner = ScriptRunner()
    script_download_queue = runner.run()

    for subscribe in updated_bangumi_obj:
        print_info('fetching %s ...' % subscribe['bangumi_name'])
        bangumi_obj = Bangumi(name=subscribe['bangumi_name'])
        bangumi_obj.select_obj()

        followed_obj = Followed(bangumi_name=subscribe['bangumi_name'])
        followed_obj.select_obj()

        # filter by subtitle group
        if not bangumi_obj or not followed_obj:
            print_error('Bangumi<{0}> does not exist or not been followed.'.format(subscribe['bangumi_name']),
                        exit_=False)
            continue

        episode, all_episode_data = website.get_maximum_episode(bangumi=bangumi_obj, ignore_old_row=ignore, max_page=1)

        if (episode.get('episode') > subscribe['episode']) or (len(ret.name) == 1 and ret.download):
            if len(ret.name) == 1 and ret.download:
                episode_range = ret.download
            else:
                episode_range = range(subscribe['episode'] + 1, episode.get('episode', 0) + 1)
                print_success('%s updated, episode: %d' % (subscribe['bangumi_name'], episode['episode']))
                followed_obj.episode = episode['episode']
                followed_obj.status = STATUS_UPDATED
                followed_obj.updated_time = int(time.time())
                followed_obj.save()

            for i in episode_range:
                for epi in all_episode_data:
                    if epi['episode'] == i:
                        download_queue.append(epi)
                        break

    if ret.download is not None:
        download_prepare(download_queue)
        download_prepare(script_download_queue)
        print_info('Re-downloading ...')
        download_prepare(Download.get_all_downloads(status=STATUS_NOT_DOWNLOAD))


def cal(ret):
    return website.bangumi_calendar(force_update=ret.force_update, today=ret.today, save=not ret.no_save)


def download_manager(ret):
    if ret.id:
        download_id = ret.id
        status = ret.status
        if download_id is None or status is None:
            print_error('No id or status specified.')
        download_obj = Download(_id=download_id)
        download_obj.select_obj()
        if not download_obj:
            print_error('Download object does not exist.')
        print_info('Download Object <{0} - {1}>, Status: {2}'.format(download_obj.name, download_obj.episode,
                                                                     download_obj.status))
        download_obj.status = status
        download_obj.save()
        print_success('Download status has been marked as {0}'.format(DOWNLOAD_CHOICE_LIST_DICT.get(int(status))))
    else:
        status = ret.status
        status = int(status) if status is not None else None
        delegate = get_download_class(instance=False)
        delegate.download_status(status=status)


def mark(ret):
    name = ret.name
    episode = ret.episode
    followed_obj = Followed(bangumi_name=name)
    followed_obj.select_obj()

    runner = ScriptRunner()

    if not followed_obj:
        followed_obj = runner.get_model(name)

    if not followed_obj:
        print_error('Subscribe or Script <%s> does not exist.' % name)

    if episode is not None:
        followed_obj.episode = episode
        followed_obj.save()
        print_success('%s has been mark as episode: %s' % (followed_obj, followed_obj.episode))
    else:
        print_info('%s, episode: %s' % (followed_obj, followed_obj.episode))


def followed(ret):
    if ret.list:
        website.bangumi_calendar(followed=True, save=False)
    else:
        mark(ret)


def list_(ret):
    website.bangumi_calendar(followed=True, save=False)


def fetch_(ret):
    bangumi_obj = Bangumi(name=ret.name)
    bangumi_obj.select_obj()

    followed_obj = Followed(bangumi_name=bangumi_obj.name)
    followed_obj.select_obj()

    followed_filter_obj = Filter(bangumi_name=ret.name)
    followed_filter_obj.select_obj()
    print_filter(followed_filter_obj)

    if bangumi_obj:
        print_info('Fetch bangumi {0} ...'.format(bangumi_obj.name))
        _, data = website.get_maximum_episode(bangumi_obj,
                                              ignore_old_row=False if ret.not_ignore else True)
        if not data:
            print_warning('Nothing.')
        for i in data:
            print_success(i['title'])

    else:
        print_error('Bangumi {0} not exist'.format(ret.name))


def search_(ret):
    if not ret.count:
        ret.count = 3

    data = website.search(ret.keyword, count=ret.count, filter_=ret.regex_filter)

    for i in data:
        print_success(i['title'])
    if ret.download:
        download_prepare(data)


def source(ret):
    if ret.source in list(map(lambda x: x['id'], SUPPORT_WEBSITE)):
        print_success('you select {}'.format(ret.source))
        DB.recreate_source_relatively_table()
        write_config('DATA_SOURCE', ret.source)
        print_success('data source switch succeeds')
        from bgmi.fetch import DATA_SOURCE_MAP

        DATA_SOURCE_MAP.get(ret.source)().bangumi_calendar(force_update=True)
    else:
        print_error(
            'please check input.nata source should be {} or {}'.format(*list(map(lambda x: x['id'], SUPPORT_WEBSITE))))


def search_without_filter(keyword):
    data = website.raw_search(keyword, count=3)
    return data


def config(ret):
    write_config(ret.name, ret.value)


CONTROLLERS_DICT = {
    ACTION_ADD: add,
    ACTION_FILTER: filter_,
    ACTION_CAL: cal,
    ACTION_DELETE: delete,
    ACTION_DOWNLOAD: download_manager,
    ACTION_UPDATE: update,
    ACTION_FETCH: fetch_,
    ACTION_CONFIG: config,
    ACTION_FOLLOWED: followed,
    ACTION_MARK: mark,
    ACTION_LIST: list_,
    ACTION_SEARCH: search_,
    ACTION_SOURCE: source,
}


def controllers(ret):
    func = CONTROLLERS_DICT.get(ret.action, None)
    if func is None or not callable(func):
        return
    else:
        return func(ret)
