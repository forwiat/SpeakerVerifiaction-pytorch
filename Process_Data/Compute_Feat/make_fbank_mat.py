#!/usr/bin/env python
# encoding: utf-8

"""
@Author: yangwenhao
@Contact: 874681044@qq.com
@Software: PyCharm
@File: make_fbank_mat.py
@Time: 2020/4/1 11:25 AM
@Overview:
"""

from __future__ import print_function
import argparse
import os
import pathlib
import sys
import pdb
from multiprocessing import Pool, Manager
import time
import numpy as np
import Process_Data.constants as c
from Process_Data.audio_processing import Make_Fbank
import scipy.io as sio


def MakeFeatsProcess(out_dir, ark_dir, proid, t_queue, e_queue):
    #  wav_scp = os.path.join(data_path, 'wav.scp')
    feat_scp = os.path.join(out_dir, 'feat.%d.scp' % proid)
    feat_mat = os.path.join(ark_dir, 'feat.%d.mat' % proid)
    utt2dur = os.path.join(out_dir, 'utt2dur.%d' % proid)
    utt2num_frames = os.path.join(out_dir, 'utt2num_frames.%d' % proid)

    feat_scp = open(feat_scp, 'w')
    utt2dur = open(utt2dur, 'w')
    utt2num_frames = open(utt2num_frames, 'w')

    feats = {}
    while not t_queue.empty():
        comm = task_queue.get()
        pair = comm.split()
        key = pair[0]

        try:
            # feat, duration = Make_Fbank(filename=pair[1], use_energy=True, nfilt=c.FILTER_BANK, duration=True)
            feat = np.load(pair[1]).astype(np.float32)
            feats[key] = feat
            feat_scp.write(str(key) + ' ' + feat_mat + ':' + key + '\n')

            utt2dur.write('%s %.6f' % (str(key), len(feat) * 0.01))
            utt2num_frames.write('%s %d' % (str(key), len(feat)))

        except:
            e_queue.put(key)

        if t_queue.qsize() % 100 == 0:
            print('\rProcess [%3s] There are [%6s] utterances' \
                  ' left, with [%6s] errors.' % (str(proid), str(t_queue.qsize()), str(e_queue.qsize())),
                  end='')

    sio.savemat(feat_mat, feats, do_compression=True)
    feat_scp.close()
    utt2dur.close()
    utt2num_frames.close()
    print('\n>> Process {} finished!'.format(proid))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Computing Filter banks!')
    parser.add_argument('--nj', type=int, default=16, metavar='E',
                        help='number of jobs to make feats (default: 10)')
    parser.add_argument('--data-dir', type=str,
                        default='/home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_dnn64/dev',
                        help='number of jobs to make feats (default: 10)')
    parser.add_argument('--out-dir', type=str,
                        default='/home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_dnn64/dev_mats',
                        help='number of jobs to make feats (default: 10)')

    parser.add_argument('--conf', type=str, default='condf/spect.conf', metavar='E',
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--vad-proportion-threshold', type=float, default=0.12, metavar='E',
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--vad-frames-context', type=int, default=2, metavar='E',
                        help='number of epochs to train (default: 10)')
    args = parser.parse_args()

    nj = args.nj
    data_dir = args.data_dir
    out_dir = args.out_dir
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    wav_scp_f = os.path.join(data_dir, 'feats.scp')
    assert os.path.exists(data_dir)
    assert os.path.exists(wav_scp_f)

    print('Copy wav.scp, spk2utt, utt2spk to %s' % out_dir)
    for f in ['wav.scp', 'spk2utt', 'utt2spk']:
        orig_f = os.path.join(data_dir, f)
        targ_f = os.path.join(out_dir, f)
        os.system('cp %s %s' % (orig_f, targ_f))

    with open(wav_scp_f, 'r') as f:
        wav_scp = f.readlines()
        assert len(wav_scp) > 0

    num_utt = len(wav_scp)
    start_time = time.time()

    manager = Manager()
    task_queue = manager.Queue()
    error_queue = manager.Queue()

    for u in wav_scp:
        task_queue.put(u)
    print('Plan to make feats for %d utterances in %s with %d jobs.' % (task_queue.qsize(), str(time.asctime()), nj))

    pool = Pool(processes=nj)  # 创建nj个进程
    for i in range(0, nj):
        write_dir = os.path.join(out_dir, 'Split%d/%d' % (nj, i))
        if not os.path.exists(write_dir):
            os.makedirs(write_dir)

        ark_dir = os.path.join(out_dir, 'fbank')
        if not os.path.exists(ark_dir):
            os.makedirs(ark_dir)

        pool.apply_async(MakeFeatsProcess, args=(write_dir, ark_dir, i, task_queue, error_queue))

    pool.close()  # 关闭进程池，表示不能在往进程池中添加进程
    pool.join()  # 等待进程池中的所有进程执行完毕，必须在close()之后调用
    if error_queue.qsize() > 0:
        print('\n>> Saving Completed with errors in: ')
        while not error_queue.empty():
            print(error_queue.get() + ' ', end='')
        print('')
    else:
        print('\n>> Saving Completed without errors.!')

    Split_dir = os.path.join(out_dir, 'Split%d' % nj)
    print('\n>> Splited Data root is %s. Concat all scripts together.' % str(Split_dir))

    all_scp_path = [os.path.join(Split_dir, '%d/feat.%d.scp' % (i, i)) for i in range(nj)]
    feat_scp = os.path.join(out_dir, 'feats.scp')
    with open(feat_scp, 'w') as feat_scp_f:
        for item in all_scp_path:
            for txt in open(item, 'r').readlines():
                feat_scp_f.write(txt)

    all_scp_path = [os.path.join(Split_dir, '%d/utt2dur.%d' % (i, i)) for i in range(nj)]
    utt2dur = os.path.join(out_dir, 'utt2dur')
    with open(utt2dur, 'w') as utt2dur_f:
        for item in all_scp_path:
            for txt in open(str(item), 'r').readlines():
                utt2dur_f.write(txt)

    all_scp_path = [os.path.join(Split_dir, '%d/utt2num_frames.%d' % (i, i)) for i in range(nj)]
    utt2num_frames = os.path.join(out_dir, 'utt2num_frames')
    with open(utt2num_frames, 'w') as utt2num_frames_f:
        for item in all_scp_path:
            for txt in open(str(item), 'r').readlines():
                utt2num_frames_f.write(txt)

    print('For multi process Completed, write all files in: %s' % out_dir)
    sys.exit()

"""
For multi threads, average making seconds for 47 speakers is 4.579958657
For one threads, average making seconds for 47 speakers is 4.11888732301

For multi process, average making seconds for 47 speakers is 1.67094940328
For one process, average making seconds for 47 speakers is 3.64203325738
"""
