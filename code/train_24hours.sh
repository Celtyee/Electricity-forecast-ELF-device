#!/bin/bash
python generate_train_dataset_buildings.py
hidden_set=()
for i in $(seq 30 2 60); do
    # shellcheck disable=SC2206
    hidden_set+=($i)
done

rnn_set=()
for i in $(seq 2 3);do
  # shellcheck disable=SC2206
  rnn_set+=($i)
done

context_set=()
for i in $(seq 7 7);do
  context_set+=($((i)))
done

for hidden in "${hidden_set[@]}";do
  for rnn in "${rnn_set[@]}";do
    for context in "${context_set[@]}"; do
      echo "Running with parameters: hidden=$hidden, rnn=$rnn, context=$context"
      python train.py --hidden_size "$hidden" --rnn_layers "$rnn" --context_day "$context" --prediction_len 1 --task_name buildings_24hours --train_dataset ../data/train/train_buildings.csv
      done
  done
done

python test_shell.py buildings_24hours 1