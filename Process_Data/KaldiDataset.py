#!/usr/bin/env python
# encoding: utf-8

"""
@Author: yangwenhao
@Contact: 874681044@qq.com
@Software: PyCharm
@File: KaldiDataset.py
@Time: 2019/12/10 下午9:28
@Overview:
"""
import os
import pathlib
import pdb
import random

import kaldi_io
import numpy as np
import torch
import torch.utils.data as data
from kaldi_io import read_mat
from tqdm import tqdm

import Process_Data.constants as c


def check_exist(path):
    if not os.path.exists(path):
        raise FileExistsError(path)

def write_xvector_ark(uid, xvector, write_path, set):
    """

    :param uid: generated by dataset class
    :param xvector:
    :param write_path:
    :param set: train or test
    :return:
    """
    file_path = pathlib.Path(write_path)
    if not file_path.exists():
        os.makedirs(str(file_path))

    ark_file = write_path+'/{}_xvector.ark'.format(set)
    scp_file = write_path+'/{}_xvector.scp'.format(set)

    # write scp and ark file


    # Prepare utt2spk file
    if set=='train':
        utt2spk_file = write_path+'/utt2spk'
        with open(utt2spk_file, 'w') as utt2spk:
            for i in range(len(uid)):
                spk = uid[i].split('-')[0]
                utt2spk.write(str(uid[i]) + ' ' + str(spk)+'\n')

        print('utt2spk file is in: {}.'.format(utt2spk_file))


def write_feat_ark(uid, feat, write_path, id):
    """
    :param uid: utterance ids generated by dataset class
    :param feat: features
    :param write_path:
    :param id: train or test
    :return:
    """
    file_path = pathlib.Path(write_path)
    if not file_path.exists():
        os.makedirs(str(file_path))

    ark_file = write_path+'/feat.{}.ark'.format(id)
    scp_file = write_path+'/feat.{}.scp'.format(id)

    # write scp and ark file
    with open(scp_file, 'w') as scp, open(ark_file, 'wb') as ark:
        for i in range(len(uid)):
            vec = feat[i]
            len_vec = len(vec.tobytes())
            key = uid[i]

            kaldi_io.write_vec_flt(ark, vec, key=key)
            # print(ark.tell())
            scp.write(str(uid[i]) + ' ' + str(ark_file) + ':' + str(ark.tell()-len_vec-10) + '\n')

    print('\nark,scp files are in: {}, {}.'.format(ark_file, scp_file))

    # Prepare utt2spk file
    # if set=='train':
    #     utt2spk_file = write_path+'/utt2spk'
    #     with open(utt2spk_file, 'w') as utt2spk:
    #         for i in range(len(uid)):
    #             spk = uid[i].split('-')[0]
    #             utt2spk.write(str(uid[i]) + ' ' + str(spk)+'\n')
    #
    #     print('utt2spk file is in: {}.'.format(utt2spk_file))


class KaldiTrainDataset(data.Dataset):
    def __init__(self, dir, samples_per_speaker, transform, num_valid=5):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        utt2spk = dir + '/utt2spk'

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1]=spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]

        utt2spk_dict = {}
        with open(utt2spk, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                utt_spk = line.split(' ')
                uid = utt_spk[0]
                if uid not in utt2spk_dict.keys():
                    utt_spk[-1] = utt_spk[-1].rstrip('\n')
                    utt2spk_dict[uid] = utt_spk[-1]
        # pdb.set_trace()

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('==> There are {} speakers in Dataset.'.format(len(speakers)))
        spk_to_idx = {speakers[i]: i for i in range(len(speakers))}
        idx_to_spk = {i: speakers[i] for i in range(len(speakers))}

        uid2feat = {}  # 'Eric_McCormack-Y-qKARMSO7k-0001.wav': feature[frame_length, feat_dim]
        pbar = tqdm(enumerate(kaldi_io.read_mat_scp(feat_scp)))
        for idx, (utt_id, feat) in pbar:
            uid2feat[utt_id] = feat

        print('\tThere are {} utterances in Train Dataset.'.format(len(uid2feat)))
        valid_set = {}
        valid_uid2feat = {}
        valid_utt2spk_dict = {}

        for spk in speakers:
            if spk not in valid_set.keys():
                valid_set[spk] = []
                for i in range(num_valid):
                    if len(dataset[spk]) <= 1:
                        break
                    j = np.random.randint(len(dataset[spk]))
                    utt = dataset[spk].pop(j)
                    valid_set[spk].append(utt)

                    valid_uid2feat[valid_set[spk][-1]] = uid2feat.pop(valid_set[spk][-1])
                    valid_utt2spk_dict[utt] = utt2spk_dict[utt]

        print('\tSpliting {} utterances for Validation.\n'.format(len(valid_uid2feat)))

        self.feat_dim = uid2feat[dataset[speakers[0]][0]].shape[1]
        self.speakers = speakers
        self.dataset = dataset
        self.valid_set = valid_set
        self.valid_uid2feat = valid_uid2feat
        self.valid_utt2spk_dict = valid_utt2spk_dict
        self.uid2feat = uid2feat
        self.spk_to_idx = spk_to_idx
        self.idx_to_spk = idx_to_spk
        self.num_spks = len(speakers)
        self.transform = transform
        self.samples_per_speaker = samples_per_speaker

    def __getitem__(self, sid):
        sid %= self.num_spks
        spk = self.idx_to_spk[sid]
        utts = self.dataset[spk]
        n_samples = 0
        y = np.array([[]]).reshape(0, self.feat_dim)

        frames = c.N_SAMPLES
        while n_samples < frames:

            uid = random.randrange(0, len(utts))
            feature = self.uid2feat[utts[uid]]

            # Get the index of feature
            if n_samples == 0:
                start = int(random.uniform(0, len(feature)))
            else:
                start = 0
            stop = int(min(len(feature) - 1, max(1.0, start + frames - n_samples)))
            try:
                y = np.concatenate((y, feature[start:stop]), axis=0)
            except:
                pdb.set_trace()
            n_samples = len(y)
            # transform features if required

        feature = self.transform(y)
        label = sid
        return feature, label

    def __len__(self):
        return self.samples_per_speaker * len(self.speakers)  # 返回一个epoch的采样数


class KaldiValidDataset(data.Dataset):
    def __init__(self, valid_set, spk_to_idx, valid_uid2feat, valid_utt2spk_dict, transform):

        speakers = [spk for spk in valid_set.keys()]
        speakers.sort()
        self.speakers = speakers
        self.dataset = valid_set
        self.valid_set = valid_set
        self.uid2feat = valid_uid2feat
        self.utt2spk_dict = valid_utt2spk_dict
        self.spk_to_idx = spk_to_idx
        self.num_spks = len(speakers)
        self.transform = transform

    def __getitem__(self, index):
        uid = list(self.uid2feat.keys())[index]
        spk = self.utt2spk_dict[uid]

        feature = self.transform(self.uid2feat[uid])
        label = self.spk_to_idx[spk]

        return feature, label

    def __len__(self):
        return len(self.uid2feat)


class KaldiTestDataset(data.Dataset):
    def __init__(self, dir, transform):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        trials = dir + '/trials'

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)
        if not os.path.exists(trials):
            raise FileExistsError(trials)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1] = spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('==> There are {} speakers in Test Dataset.'.format(len(speakers)))

        uid2feat = {}
        for utt_id, feat in kaldi_io.read_mat_scp(feat_scp):
            uid2feat[utt_id] = feat
        print('\tThere are {} utterances in Test Dataset.'.format(len(uid2feat)))

        trials_pair = []
        with open(trials, 'r') as t:
            all_pairs = t.readlines()
            for line in all_pairs:
                pair = line.split(' ')
                if pair[2] == 'nontarget\n':
                    pair_true = False
                else:
                    pair_true = True

                trials_pair.append((pair[0], pair[1], pair_true))

        print('\tThere are {} pairs in test Dataset.\n'.format(len(trials_pair)))

        self.feat_dim = uid2feat[dataset[speakers[0]][0]].shape[1]
        self.speakers = speakers
        self.uid2feat = uid2feat
        self.trials_pair = trials_pair
        self.num_spks = len(speakers)
        self.transform = transform

    def __getitem__(self, index):
        uid_a, uid_b, label = self.trials_pair[index]

        data_a = self.uid2feat[uid_a]
        data_b = self.uid2feat[uid_b]

        data_a = self.transform(data_a)
        data_b = self.transform(data_b)

        return data_a, data_b, label

    def __len__(self):
        return len(self.trials_pair)


class TrainDataset(data.Dataset):
    def __init__(self, dir, transform):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        utt2spk = dir + '/utt2spk'
        num_valid = 5

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1]=spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]
        utt2spk_dict = {}
        with open(utt2spk, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                utt_spk = line.split(' ')
                uid = utt_spk[0]
                if uid not in utt2spk_dict.keys():
                    utt_spk[-1] = utt_spk[-1].rstrip('\n')
                    utt2spk_dict[uid] = utt_spk[-1]
        # pdb.set_trace()

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('==>There are {} speakers in Dataset.'.format(len(speakers)))
        spk_to_idx = {speakers[i]: i for i in range(len(speakers))}
        idx_to_spk = {i: speakers[i] for i in range(len(speakers))}

        uid2feat = {}  # 'Eric_McCormack-Y-qKARMSO7k-0001.wav': feature[frame_length, feat_dim]
        pbar = tqdm(enumerate(kaldi_io.read_mat_scp(feat_scp)))
        for idx, (utt_id, feat) in pbar:
            uid2feat[utt_id] = feat

        print('==>There are {} utterances in Train Dataset.'.format(len(uid2feat)))
        valid_set = {}
        valid_uid2feat = {}
        valid_utt2spk_dict = {}

        for spk in speakers:
            if spk not in valid_set.keys():
                valid_set[spk] = []
                for i in range(num_valid):
                    if len(dataset[spk]) <= 1:
                        break
                    j = np.random.randint(len(dataset[spk]))
                    utt = dataset[spk].pop(j)
                    valid_set[spk].append(utt)

                    valid_uid2feat[valid_set[spk][-1]] = uid2feat.pop(valid_set[spk][-1])
                    valid_utt2spk_dict[utt] = utt2spk_dict[utt]

        print('==>Spliting {} utterances for Validation.\n'.format(len(valid_uid2feat)))
        utt_lst = []
        for uid in list(utt2spk_dict.keys()):
            if uid not in valid_uid2feat.keys():
                utt_lst.append(uid)
        random.shuffle(utt_lst)

        self.feat_dim = uid2feat[dataset[speakers[0]][0]].shape[1]
        self.speakers = speakers
        self.dataset = dataset
        self.utt_lst = utt_lst
        self.utt2spk_dict = utt2spk_dict
        self.valid_set = valid_set
        self.valid_uid2feat = valid_uid2feat
        self.valid_utt2spk_dict = valid_utt2spk_dict
        self.uid2feat = uid2feat
        self.spk_to_idx = spk_to_idx
        self.idx_to_spk = idx_to_spk
        self.num_spks = len(speakers)
        self.transform = transform

    def __getitem__(self, sid):
        uid = self.utt_lst[sid]
        spk = self.utt2spk_dict[uid]

        feat = self.uid2feat[uid]
        feature = self.transform(feat)

        label = self.spk_to_idx[spk]
        return feature, label

    def __len__(self):
        return len(self.utt_lst)  # 返回一个epoch的采样数


class KaldiTupleDataset(data.Dataset):
    def __init__(self, dir, transform, samples_per_spk=150, num_valid=5, num_enroll=5, nagative_pair=1):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        utt2spk = dir + '/utt2spk'
        train_trials = dir + '/train.trials'

        self.num_enroll = num_enroll

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1]=spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]

        utt2spk_dict = {}
        with open(utt2spk, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                utt_spk = line.split(' ')
                uid = utt_spk[0]
                if uid not in utt2spk_dict.keys():
                    utt_spk[-1] = utt_spk[-1].rstrip('\n')
                    utt2spk_dict[uid] = utt_spk[-1]
        # pdb.set_trace()

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('==> There are {} speakers in Dataset.'.format(len(speakers)))
        spk_to_idx = {speakers[i]: i for i in range(len(speakers))}
        idx_to_spk = {i: speakers[i] for i in range(len(speakers))}


        uid2feat = {}  # 'Eric_McCormack-Y-qKARMSO7k-0001.wav': feature[frame_length, feat_dim]
        pbar = tqdm(enumerate(kaldi_io.read_mat_scp(feat_scp)))
        for idx, (utt_id, feat) in pbar:
            uid2feat[utt_id] = feat

        print('\tThere are {} utterances in Train Dataset.'.format(len(uid2feat)))
        valid_set = {}
        valid_uid2feat = {}
        valid_utt2spk_dict = {}

        for spk in speakers:
            if spk not in valid_set.keys():
                valid_set[spk] = []
                for i in range(num_valid):
                    if len(dataset[spk]) <= 1:
                        break
                    j = np.random.randint(len(dataset[spk]))
                    utt = dataset[spk].pop(j)
                    valid_set[spk].append(utt)

                    valid_uid2feat[valid_set[spk][-1]] = uid2feat.pop(valid_set[spk][-1])
                    valid_utt2spk_dict[utt] = utt2spk_dict[utt]

        print('\tSpliting {} utterances for Validation.\n'.format(len(valid_uid2feat)))

        tuple_lst = []
        train_trials_f = open(train_trials, 'w')
        for i in range(len(speakers)):
            spk = speakers[i]
            for j in range(samples_per_spk):
                eval_utts = dataset[spk].copy()
                positive_eval_idx = np.random.randint(0, len(eval_utts))
                eval_utt = eval_utts[positive_eval_idx]
                eval_utts.pop(positive_eval_idx)
                positive_enroll = np.random.choice(eval_utts, size=num_enroll)

                positive_trials = []
                positive_trials.append(eval_utt)
                for x in positive_enroll:
                    positive_trials.append(x)

                positive_trials.append('1')
                positive_trials.append(str(spk_to_idx[spk]))
                for m in range(num_enroll):
                    positive_trials.append(str(spk_to_idx[spk]))

                tuple_lst.append(positive_trials)
                train_trials_f.write(' '.join(positive_trials) + '\n')

                nagative_spks = speakers.copy()
                nagative_spks.pop(i)

                nagative_spks = np.random.choice(nagative_spks, size=nagative_pair, replace=False)
                for nagative_spk in nagative_spks:
                    negative_trials = []
                    negative_trials.append(eval_utt)
                    nagative_enroll = np.random.choice(dataset[nagative_spk], size=num_enroll)
                    for x in nagative_enroll:
                        negative_trials.append(x)

                    negative_trials.append('0')
                    negative_trials.append(str(spk_to_idx[spk]))
                    for m in range(num_enroll):
                        negative_trials.append(str(spk_to_idx[nagative_spk]))

                    tuple_lst.append(negative_trials)
                    train_trials_f.write(' '.join(negative_trials) + '\n')

        train_trials_f.close()

        print('\tGenerate {} tuples for training.\n'.format(len(tuple_lst)))


        self.feat_dim = uid2feat[dataset[speakers[0]][0]].shape[1]
        self.speakers = speakers
        self.dataset = dataset
        self.valid_set = valid_set
        self.valid_uid2feat = valid_uid2feat
        self.valid_utt2spk_dict = valid_utt2spk_dict
        self.uid2feat = uid2feat
        self.spk_to_idx = spk_to_idx
        self.idx_to_spk = idx_to_spk
        self.num_spks = len(speakers)
        self.transform = transform
        self.samples_per_spk = samples_per_spk
        self.tuple_lst = tuple_lst

    def __getitem__(self, sid):
        # pdb.set_trace()
        pairs = self.tuple_lst[sid]
        uids = pairs[:self.num_enroll+1]
        labels = pairs[self.num_enroll+1:]
        labels = [int(x) for x in labels]

        feat_uids = [self.uid2feat[uid] for uid in uids]
        feats = [self.transform(feat) for feat in feat_uids]
        features = torch.cat(feats, dim=0)
        # features = np.concatenate(feat_uids, axis=0)
        labels = torch.LongTensor(labels)

        # features:   eval_utt,    utt1,  ...  ,    utt5
        # labels:0/1, spk_idx1,spk_idx2,  ...  ,spk_idx2
        return features, labels

    def __len__(self):
        return len(self.tuple_lst)  # 返回一个epoch的采样数


class KaldiExtractDataset(data.Dataset):
    def __init__(self, dir, samples_per_speaker, transform, num_valid=5):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        utt2spk = dir + '/utt2spk'

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1] = spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]

        utt2spk_dict = {}
        with open(utt2spk, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                utt_spk = line.split(' ')
                uid = utt_spk[0]
                if uid not in utt2spk_dict.keys():
                    utt_spk[-1] = utt_spk[-1].rstrip('\n')
                    utt2spk_dict[uid] = utt_spk[-1]
        # pdb.set_trace()

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('==> There are {} speakers in Dataset.'.format(len(speakers)))
        spk_to_idx = {speakers[i]: i for i in range(len(speakers))}
        idx_to_spk = {i: speakers[i] for i in range(len(speakers))}

        uid2feat = {}  # 'Eric_McCormack-Y-qKARMSO7k-0001.wav': feature[frame_length, feat_dim]
        pbar = tqdm(enumerate(kaldi_io.read_mat_scp(feat_scp)))
        for idx, (utt_id, feat) in pbar:
            uid2feat[utt_id] = feat

        print('==> There are {} utterances in Train Dataset.'.format(len(uid2feat)))
        valid_set = {}
        valid_uid2feat = {}
        valid_utt2spk_dict = {}

        for spk in speakers:
            if spk not in valid_set.keys():
                valid_set[spk] = []
                for i in range(num_valid):
                    if len(dataset[spk]) <= 1:
                        break
                    j = np.random.randint(len(dataset[spk]))
                    utt = dataset[spk].pop(j)
                    utt2spk_dict.pop(utt)
                    valid_set[spk].append(utt)

                    valid_uid2feat[valid_set[spk][-1]] = uid2feat.pop(valid_set[spk][-1])
                    valid_utt2spk_dict[utt] = utt2spk_dict[utt]

        print('==> Spliting {} utterances for Validation.\n'.format(len(valid_uid2feat)))

        self.feat_dim = uid2feat[dataset[speakers[0]][0]].shape[1]
        self.speakers = speakers
        self.dataset = dataset
        self.valid_set = valid_set
        self.valid_uid2feat = valid_uid2feat
        self.valid_utt2spk_dict = valid_utt2spk_dict
        self.uid2feat = uid2feat
        self.spk_to_idx = spk_to_idx
        self.idx_to_spk = idx_to_spk
        self.num_spks = len(speakers)
        self.transform = transform
        self.samples_per_speaker = samples_per_speaker
        self.uids = list(self.uid2feat.keys())
        self.utt2spk_dict = utt2spk_dict

    def __getitem__(self, index):
        uid = self.uids[index]
        y = self.uid2feat[uid]
        feature = self.transform(y)

        spk = self.utt2spk[uid]
        label = self.spk_to_idx[spk]

        return feature, label, uid

    def __len__(self):
        return len(self.uid2feat)  # 返回一个epoch的采样数


class ScriptTrainDataset(data.Dataset):
    def __init__(self, dir, samples_per_speaker, transform, num_valid=5, loader=np.load, return_uid=False):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        utt2spk = dir + '/utt2spk'

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1] = spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]

        utt2spk_dict = {}
        with open(utt2spk, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                utt_spk = line.split(' ')
                uid = utt_spk[0]
                if uid not in utt2spk_dict.keys():
                    utt_spk[-1] = utt_spk[-1].rstrip('\n')
                    utt2spk_dict[uid] = utt_spk[-1]
        # pdb.set_trace()

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('==> There are {} speakers in Dataset.'.format(len(speakers)))
        spk_to_idx = {speakers[i]: i for i in range(len(speakers))}
        idx_to_spk = {i: speakers[i] for i in range(len(speakers))}

        uid2feat = {}  # 'Eric_McCormack-Y-qKARMSO7k-0001.wav': feature[frame_length, feat_dim]
        with open(feat_scp, 'r') as f:
            for line in f.readlines():
                uid, feat_offset = line.split()
                uid2feat[uid] = feat_offset

        print('    There are {} utterances in Train Dataset.'.format(len(uid2feat)))
        valid_set = {}
        valid_uid2feat = {}
        valid_utt2spk_dict = {}

        for spk in speakers:
            if spk not in valid_set.keys():
                valid_set[spk] = []
                for i in range(num_valid):
                    if len(dataset[spk]) <= 1:
                        break
                    j = np.random.randint(len(dataset[spk]))
                    utt = dataset[spk].pop(j)
                    valid_set[spk].append(utt)

                    valid_uid2feat[valid_set[spk][-1]] = uid2feat.pop(valid_set[spk][-1])
                    valid_utt2spk_dict[utt] = utt2spk_dict[utt]

        print('    Spliting {} utterances for Validation.'.format(len(valid_uid2feat)))

        self.speakers = speakers
        self.dataset = dataset
        self.valid_set = valid_set
        self.valid_uid2feat = valid_uid2feat
        self.valid_utt2spk_dict = valid_utt2spk_dict
        self.uid2feat = uid2feat
        self.spk_to_idx = spk_to_idx
        self.idx_to_spk = idx_to_spk
        self.num_spks = len(speakers)

        self.loader = loader
        self.feat_dim = loader(uid2feat[dataset[speakers[0]][0]]).shape[1]
        self.transform = transform
        self.samples_per_speaker = samples_per_speaker
        self.return_uid = return_uid

        if self.return_uid:
            self.utt_dataset = []
            for i in range(self.samples_per_speaker * self.num_spks):
                sid = i % self.num_spks
                spk = self.idx_to_spk[sid]
                utts = self.dataset[spk]
                uid = utts[random.randrange(0, len(utts))]
                self.utt_dataset.append([uid, sid])


    def __getitem__(self, sid):

        if self.return_uid:
            uid, label = self.utt_dataset[sid]
            y = self.loader(self.uid2feat[uid])
            feature = self.transform(y)
            return feature, label, uid

        sid %= self.num_spks
        spk = self.idx_to_spk[sid]
        utts = self.dataset[spk]

        n_samples = 0
        y = np.array([[]]).reshape(0, self.feat_dim)

        frames = c.N_SAMPLES
        while n_samples < frames:

            uid = random.randrange(0, len(utts))
            feature = self.loader(self.uid2feat[utts[uid]])

            # Get the index of feature
            if n_samples == 0:
                start = int(random.uniform(0, len(feature)))
            else:
                start = 0
            stop = int(min(len(feature) - 1, max(1.0, start + frames - n_samples)))
            y = np.concatenate((y, feature[start:stop]), axis=0)
            n_samples = len(y)
            # transform features if required

        feature = self.transform(y)
        label = sid
        return feature, label

    def __len__(self):
        return self.samples_per_speaker * len(self.speakers)  # 返回一个epoch的采样数


class ScriptValidDataset(data.Dataset):
    def __init__(self, valid_set, spk_to_idx, valid_uid2feat, valid_utt2spk_dict, transform, loader=np.load,
                 return_uid=False):
        speakers = [spk for spk in valid_set.keys()]
        speakers.sort()
        self.speakers = speakers
        self.dataset = valid_set
        self.valid_set = valid_set
        self.uid2feat = valid_uid2feat

        uids = list(valid_uid2feat.keys())
        uids.sort()
        print(uids[:10])
        self.uids = uids
        self.utt2spk_dict = valid_utt2spk_dict
        self.spk_to_idx = spk_to_idx
        self.num_spks = len(speakers)

        self.loader = loader
        self.transform = transform
        self.return_uid = return_uid

    def __getitem__(self, index):
        uid = self.uids[index]
        spk = self.utt2spk_dict[uid]
        y = self.loader(self.uid2feat[uid])

        feature = self.transform(y)
        label = self.spk_to_idx[spk]

        if self.return_uid:
            return feature, label, uid

        return feature, label

    def __len__(self):
        return len(self.uids)


class ScriptTestDataset(data.Dataset):
    def __init__(self, dir, transform, loader=np.load, return_uid=False):

        feat_scp = dir + '/feats.scp'
        spk2utt = dir + '/spk2utt'
        trials = dir + '/trials'

        if not os.path.exists(feat_scp):
            raise FileExistsError(feat_scp)
        if not os.path.exists(spk2utt):
            raise FileExistsError(spk2utt)
        if not os.path.exists(trials):
            raise FileExistsError(trials)

        dataset = {}
        with open(spk2utt, 'r') as u:
            all_cls = u.readlines()
            for line in all_cls:
                spk_utt = line.split(' ')
                spk_name = spk_utt[0]
                if spk_name not in dataset.keys():
                    spk_utt[-1] = spk_utt[-1].rstrip('\n')
                    dataset[spk_name] = spk_utt[1:]

        speakers = [spk for spk in dataset.keys()]
        speakers.sort()
        print('    There are {} speakers in Test Dataset.'.format(len(speakers)))

        uid2feat = {}
        with open(feat_scp, 'r') as f:
            for line in f.readlines():
                uid, feat_offset = line.split()
                uid2feat[uid] = feat_offset

        print('    There are {} utterances in Test Dataset.'.format(len(uid2feat)))

        trials_pair = []
        positive_pairs = 0
        with open(trials, 'r') as t:
            all_pairs = t.readlines()
            for line in all_pairs:
                pair = line.split()
                if pair[2] == 'nontarget' or pair[2] == '0':
                    pair_true = False
                else:
                    pair_true = True
                    positive_pairs += 1

                trials_pair.append((pair[0], pair[1], pair_true))
        trials_pair = np.array(trials_pair)
        trials_pair = trials_pair[trials_pair[:, 2].argsort()[::-1]]

        print('==>There are {} pairs in test Dataset with {} positive pairs'.format(len(trials_pair), positive_pairs))

        self.feat_dim = loader(uid2feat[dataset[speakers[0]][0]]).shape[1]
        self.speakers = speakers
        self.uid2feat = uid2feat
        self.trials_pair = trials_pair
        self.num_spks = len(speakers)
        self.numofpositive = positive_pairs

        self.loader = loader
        self.transform = transform
        self.return_uid = return_uid

    def __getitem__(self, index):
        uid_a, uid_b, label = self.trials_pair[index]

        feat_a = self.uid2feat[uid_a]
        feat_b = self.uid2feat[uid_b]
        y_a = self.loader(feat_a)
        y_b = self.loader(feat_b)

        data_a = self.transform(y_a)
        data_b = self.transform(y_b)

        if label == 'True' or label == True:
            label = True
        else:
            label = False

        if self.return_uid:
            # pdb.set_trace()
            # print(uid_a, uid_b)
            data_a, data_b, [label, uid_a, uid_b]
        else:
            return data_a, data_b, label

    def partition(self, num):
        if num > len(self.trials_pair):
            print('%d is greater than the total number of pairs')

        elif num * 0.3 > self.numofpositive:
            indices = list(range(self.numofpositive, len(self.trials_pair)))
            random.shuffle(indices)
            indices = indices[:(num - self.numofpositive)]
            positive_idx = list(range(self.numofpositive))

            positive_pairs = self.trials_pair[positive_idx].copy()
            nagative_pairs = self.trials_pair[indices].copy()

            self.trials_pair = np.concatenate((positive_pairs, nagative_pairs), axis=0)
        else:
            indices = list(range(self.numofpositive, len(self.trials_pair)))
            random.shuffle(indices)
            indices = indices[:(num - int(0.3 * num))]

            positive_idx = list(range(self.numofpositive))
            random.shuffle(positive_idx)
            positive_idx = positive_idx[:int(0.3 * num)]
            positive_pairs = self.trials_pair[positive_idx].copy()
            nagative_pairs = self.trials_pair[indices].copy()

            self.numofpositive = len(positive_pairs)
            self.trials_pair = np.concatenate((positive_pairs, nagative_pairs), axis=0)

        assert len(self.trials_pair) == num
        num_positive = 0
        for x, y, z in self.trials_pair:
            if z == 'True':
                num_positive += 1

        assert len(self.trials_pair) == num, '%d != %d' % (len(self.trials_pair), num)
        assert self.numofpositive == num_positive, '%d != %d' % (self.numofpositive, num_positive)
        print('%d positive pairs remain.' % num_positive)


    def __len__(self):
        return len(self.trials_pair)


class SitwTestDataset(data.Dataset):
    """

    """

    def __init__(self, sitw_dir, sitw_set, transform, loader=read_mat, return_uid=False, set_suffix='no_sil'):
        # sitw_set: dev, eval
        feat_scp = sitw_dir + '/%s%s/feats.scp' % (sitw_set, set_suffix)
        spk2utt = sitw_dir + '/%s%s/spk2utt' % (sitw_set, set_suffix)
        trials = sitw_dir + '/%s%s/trials' % (sitw_set, set_suffix)

        for p in feat_scp, spk2utt, trials:
            check_exist(p)

        uid2feat = {}
        with open(feat_scp, 'r') as t:
            all_pairs = t.readlines()
            for line in all_pairs:
                # 12013 lpnns target
                pair = line.split()
                uid2feat[pair[0]] = pair[1]

        trials_pair = []
        numofpositive = 0
        with open(trials, 'r') as t:
            all_pairs = t.readlines()
            for line in all_pairs:
                # 12013 lpnns target
                pair = line.split()
                if pair[2] == 'nontarget':
                    pair_true = False
                else:
                    pair_true = True
                    numofpositive += 1

                trials_pair.append((pair[0], pair[1], pair_true))

        trials_pair = np.array(trials_pair)
        trials_pair = trials_pair[trials_pair[:, 2].argsort()[::-1]]

        print('==>There are %d pairs in sitw %s Dataset %d of them are positive.' % (
        len(trials_pair), sitw_set, numofpositive))
        # pdb.set_trace()
        self.feat_dim = loader(uid2feat[trials_pair[0][0]]).shape[1]

        self.pairs = len(trials_pair)
        self.numofpositive = numofpositive
        self.uid2feat = uid2feat
        self.trials_pair = trials_pair
        self.loader = loader
        self.transform = transform
        self.return_uid = return_uid

    def __getitem__(self, index):
        uid_a, uid_b, label = self.trials_pair[index]

        data_a = self.loader(self.uid2feat[uid_a])
        data_b = self.loader(self.uid2feat[uid_b])

        data_a = self.transform(data_a)
        data_b = self.transform(data_b)
        if label == 'True' or label == True:
            label = True
        else:
            label = False

        if self.return_uid:
            return data_a, data_b, label, uid_a, uid_b
        else:
            return data_a, data_b, label

    def partition(self, num):
        if num > self.pairs:
            print('%d is greater than the total number of pairs')

        elif num * 0.3 > self.numofpositive:
            indices = list(range(self.numofpositive, len(self.trials_pair)))
            random.shuffle(indices)
            indices = indices[:(num - self.numofpositive)]
            positive_idx = list(range(self.numofpositive))

            positive_pairs = self.trials_pair[positive_idx].copy()
            nagative_pairs = self.trials_pair[indices].copy()

            self.trials_pair = np.concatenate((positive_pairs, nagative_pairs), axis=0)
        else:
            indices = list(range(self.numofpositive, len(self.trials_pair)))
            random.shuffle(indices)
            indices = indices[:(num - int(0.3 * num))]

            positive_idx = list(range(self.numofpositive))
            random.shuffle(positive_idx)
            positive_idx = positive_idx[:int(0.3 * num)]
            positive_pairs = self.trials_pair[positive_idx].copy()
            nagative_pairs = self.trials_pair[indices].copy()

            self.numofpositive = len(positive_pairs)
            self.trials_pair = np.concatenate((positive_pairs, nagative_pairs), axis=0)

        assert len(self.trials_pair) == num
        num_positive = 0
        for x, y, z in self.trials_pair:
            if z == 'True':
                num_positive += 1

        assert len(self.trials_pair) == num, '%d != %d' % (len(self.trials_pair), num)
        assert self.numofpositive == num_positive, '%d != %d' % (self.numofpositive, num_positive)
        print('%d positive pairs remain.' % num_positive)

    def __len__(self):
        return len(self.trials_pair)

# uid = ['A.J._Buckley-1zcIwhmdeo4-0001.wav', 'A.J._Buckley-1zcIwhmdeo4-0002.wav', 'A.J._Buckley-1zcIwhmdeo4-0003.wav', 'A.J._Buckley-7gWzIy6yIIk-0001.wav']
# xvector = np.random.randn(4, 512).astype(np.float32)
#
# ark_file = '../Data/xvector.ark'
# scp_file = '../Data/xvector.scp'
#
# write_xvector_ark(uid, xvector, ark_file, scp_file)

