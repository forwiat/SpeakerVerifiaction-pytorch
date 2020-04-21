#!/usr/bin/env bash

stage=1
waited=0
while [ `ps 45442 | wc -l` -eq 2 ]; do
  sleep 60
  waited=$(expr $waited + 1)
  echo -en "\033[1;4;31m Having waited for ${waited} minutes!\033[0m\r"
done

if [ $stage -le 0 ]; then
  model=ETDNN
  for loss in soft ; do
    python TrainAndTest/Fbank/TDNNs/train_etdnn_kaldi.py \
      --train-dir /home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_pyfb80/dev_kaldi \
      --test-dir /home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_pyfb80/test_kaldi \
      --check-path Data/checkpoint/${model}/fbank80/soft \
      --resume Data/checkpoint/${model}/fbank80/soft/checkpoint_1.pth
      --epochs 20 \
      --milestones 10,15  \
      --feat-dim 80 \
      --embedding-size 256 \
      --num-valid 2 \
      --loss-type soft \
      --lr 0.01

  done
fi

#stage=1
if [ $stage -le 5 ]; then
  model=TDNN
  feat=fb40
  for loss in soft ; do
    python TrainAndTest/Fbank/TDNNs/train_tdnn_kaldi.py \
      --model ${model} \
      --train-dir /home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_pyfb/dev_fb40 \
      --test-dir /home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_pyfb/test_fb40 \
      --check-path Data/checkpoint/${model}/${feat}/${loss} \
      --resume Data/checkpoint/${model}/${feat}/${loss}/checkpoint_1.pth \
      --epochs 20 \
      --milestones 10,15  \
      --feat-dim 40 \
      --embedding-size 512 \
      --num-valid 2 \
      --loss-type ${loss} \
      --lr 0.01
  done
fi

stage=100
if [ $stage -le 10 ]; then
  model=ASTDNN
  feat=mfcc40
  for loss in soft ; do
    python TrainAndTest/Fbank/TDNNs/train_astdnn_kaldi.py \
      --train-dir /home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_pymfcc40/dev_kaldi \
      --test-dir /home/yangwenhao/local/project/lstm_speaker_verification/data/Vox1_pymfcc40/test_kaldi \
      --check-path Data/checkpoint/${model}/${feat}/${loss} \
      --resume Data/checkpoint/${model}/${feat}/${loss}/checkpoint_1.pth \
      --epochs 20 \
      --milestones 10,15  \
      --feat-dim 40 \
      --embedding-size 512 \
      --num-valid 2 \
      --loss-type ${loss} \
      --lr 0.01
  done
fi