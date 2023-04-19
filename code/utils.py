import numpy as np
import torch
import datetime
import re
import json
import os
import warnings
import pandas as pd

import matplotlib.pyplot as plt
import pytorch_lightning as pl
from pytorch_lightning.callbacks import EarlyStopping
from pytorch_forecasting import DeepAR, TimeSeriesDataSet
from pytorch_forecasting.data import NaNLabelEncoder

warnings.filterwarnings("ignore")


def remove_unit(x):
    pattern = r"([-+]?\d*\.\d+|\d+)"  # 匹配数值部分的正则表达式
    match = re.search(pattern, x)  # 搜索匹配结果
    if match is not None:
        return float(match.group(0))  # 返回数值部分
    else:
        return x


def check_incomplete_electricity_dt(electricity_csv):
    # Load the data into a pandas dataframe
    df = pd.read_csv(electricity_csv)

    # Convert the timestamp column to datetime type
    df['time'] = pd.to_datetime(df['time'])

    # Set the timestamp column as the index of the dataframe
    df.set_index('time', inplace=True)

    # Resample the dataframe to hourly frequency
    df_resampled = df.resample('H').mean()

    # Get the list of dates where the resampled data is missing
    missing_dates = df_resampled[df_resampled.isna().any(axis=1)].index.strftime('%Y-%m-%d').unique().tolist()

    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    program_name = "logger"
    logger = open(f"{program_name}.log", 'w')
    logger.write(f"\n\n\nThe program 'check_incomplete_electricity_dt' is running at {current_time}\n")
    # Print the missing dates
    logger.write("Dates with non-hourly data:\n")

    count = 0
    for date in missing_dates:
        if count % 5 == 0:
            logger.write("\n")
        logger.write(f" {str(date)} ")
        count += 1


# generator the dataset containing weather condition and
def refine_timestamp(total_csv_save_path):
    # Read CSV file into a Pandas DataFrame
    df = pd.read_csv(total_csv_save_path)

    # Combine date and time columns into a single datetime column
    df['datetime'] = df.apply(
        lambda x: datetime.datetime.strptime(x['Date'] + ' ' + x['Time'], '%Y-%m-%d %I:%M %p'), axis=1)
    # Format datetime column as a string in the desired format
    df['timestamp'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
    df = df.drop(['datetime', 'Date', 'Time'], axis=1)
    # move the 'timestamp' to first
    cols = list(df.columns)
    cols = [cols[-1]] + cols[:-1]
    df = df[cols]
    df.to_csv(total_csv_save_path, index=False)


class dataset_generator:
    def __init__(self, weather, electricity):
        self.daily_weather_folder = f'{weather}/daily_weather'
        self.history_weather_folder = weather
        self.history_electricity_folder = electricity

    def generate_dataset(self, building_list, start_date, end_date, weather):
        '''
        generate the electricity usage dataset consists of weather condition, building ID, electricity usage.

        Parameters
        ----------
        building_list: list of strings
        start_date: datetime.datetime.date() data
        end_date: datetime.datetime.date() data
        weather: compressed weather data file

        Returns
        -------

        '''
        name_list = building_list
        df_list = []
        # generate the weather data for 10 buildings
        df_wtr = pd.read_csv(weather)[1::2]
        df_wtr['timestamp'] = pd.to_datetime(df_wtr['timestamp'])

        mask_wtr = (df_wtr['timestamp'].dt.date >= start_date) & (df_wtr['timestamp'].dt.date <= end_date)
        weather_sub = df_wtr[mask_wtr][:]

        for building in name_list:
            df_ele = pd.read_csv(f'{self.history_electricity_folder}/{building}.csv')
            # Turn from UTC into UTC+8
            df_ele['time'] = pd.to_datetime(df_ele['time']) + datetime.timedelta(hours=8)

            mask_ele = (df_ele['time'].dt.date >= start_date) & (df_ele['time'].dt.date <= end_date)
            df_ele[df_ele['val'] <= 0]['val'] = 100000
            df_ele.fillna(method="pad")
            if building == "1A":
                df_ele.to_csv(f"./{building}.csv")
            electricity_sub = df_ele[mask_ele]['val'][1:]
            training_df = pd.concat((weather_sub.reset_index(drop=True), electricity_sub.reset_index(drop=True)),
                                    axis=1)

            training_df['Building'] = building
            training_df['time_idx'] = range(len(training_df))
            # the 'val' is the electricity consumption between 'time_index' and 'time_index' + 1hour
            # add whether this hour is holiday or weekend
            # print(training_df.columns)
            training_df['is_weekend'] = training_df['timestamp'].dt.dayofweek.isin([5, 6])
            df_list.append(training_df)

        return df_list

    def __check_incomplete_date(self):
        std_shape = (48, 11)
        program_name = "logger"
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        folder_path = self.daily_weather_folder
        # clear the logger
        logger = open(f"{program_name}.log", 'w')
        logger.write("\n")
        logger.close()

        logger = open(f"{program_name}.log", 'a')
        logger.write(f"The program '{program_name}' is running at {current_time}\n")
        incomplete_weather = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                csv_file = os.path.join(root, file)
                obj_file = pd.read_csv(csv_file)
                if obj_file.shape != std_shape:
                    logger.write(f"inconsistent file:{file}, the corresponding shape is {obj_file.shape}\n")
                    incomplete_weather.append(file[7:17])
        logger.close()
        return incomplete_weather

    def compress_weather_data(self, total_csv_save_path):
        '''
        Compress the all daily weather data into one file, removing the units.

        Parameters
        ----------
        total_csv_save_path

        Returns
        -------

        '''
        incomplete_date = self.__check_incomplete_date()
        daily_folder = self.daily_weather_folder
        weather_list = []
        for root, dirs, files in os.walk(daily_folder):
            for file in sorted(files):
                # print(f"Now we are processing csv file {file}")
                csv_file = os.path.join(root, file)
                weather = pd.read_csv(csv_file)
                # # find the days when data are lost.
                date = file[7:17]
                if date in incomplete_date:
                    continue
                weather.iloc[:, 2:] = weather.iloc[:, 2:].applymap(remove_unit)
                weather_list.append(weather)

        weather_df = pd.concat(weather_list)
        weather_df.to_csv(total_csv_save_path, index=False)
        refine_timestamp(total_csv_save_path)


# define the network and find the optimal learning rate for the specific task
def train_model(time_series_dataset, dataloader_train, dataloader_val, hidden_size=30, rnn_layers=2,
                save_folder="./", min_lr=1e-5):
    trainer = pl.Trainer(gpus=1, gradient_clip_val=1e-1)
    net = DeepAR.from_dataset(
        time_series_dataset, learning_rate=3e-2, hidden_size=hidden_size, rnn_layers=rnn_layers
    )

    # find optimal learning rate
    res = trainer.tuner.lr_find(
        net,
        train_dataloaders=dataloader_train,
        val_dataloaders=dataloader_val,
        min_lr=min_lr,
        max_lr=1e0,
        early_stop_threshold=100
    )

    print(f"suggested learning rate: {res.suggestion()}")
    fig = res.plot(show=True, suggest=True)
    fig.savefig(f"{save_folder}/res.png")
    net.hparams.learning_rate = res.suggestion()

    # start train
    early_stop_callback = EarlyStopping(monitor="val_loss", min_delta=1e-4, patience=10, verbose=False, mode="min")
    trainer = pl.Trainer(
        max_epochs=50,
        gpus=1,
        enable_model_summary=True,
        gradient_clip_val=1e-2,
        callbacks=[early_stop_callback],
        limit_train_batches=50,
        enable_checkpointing=True,
    )

    trainer.fit(
        net,
        train_dataloaders=dataloader_train,
        val_dataloaders=dataloader_val,
    )

    trainer.save_checkpoint(f"{save_folder}/checkpoint.ckpt")
    return net


def validation_model(net, save_folder, timeseries_val, dataloader_val):
    model = DeepAR.load_from_checkpoint(f"{save_folder}/checkpoint.ckpt")
    actuals = torch.cat([y[0] for x, y in iter(dataloader_val)])
    predictions = model.predict(dataloader_val)
    loss = ((actuals - predictions).abs().mean())
    raw_predictions, x = net.predict(dataloader_val, mode="raw", return_x=True, n_samples=100)
    # print(type(x), type(raw_predictions))
    series = timeseries_val.x_to_index(x)["Building"]
    for idx in range(len(series)):  # plot 10 examples
        model.plot_prediction(x, raw_predictions, idx=idx,
                              add_loss_to_title=True)
        building = series.iloc[idx]
        plt.suptitle(f"Building: {building}")
        plt.savefig(f"{save_folder}/plot_{building}_encoder.png")

    return loss


class my_deepAR_model:
    def __init__(self, pl_ckpt, context_length, predictor_length, building):
        self.model = DeepAR.load_from_checkpoint(pl_ckpt)
        self.building_series = building
        self.context_length = context_length
        self.predictor_length = predictor_length

    def predict(self, history_data):
        data = pd.read_csv(history_data)
        data = data.drop(['Wind', 'Precip.', 'Wind Gust'], axis=1)
        data = data.fillna(method='pad')
        cutoff = data["time_idx"].max() - self.predictor_length

        # print(f'The size of data is {len(data[lambda x: x["time_idx"] <= cutoff])}')
        #
        # print(f'The cutoff is {cutoff}')  # 359
        # print(f'The max of time_idx is {data["time_idx"].max()}')  # 527
        # print(f'The context length is {self.context_length}')  # 336
        # print(f'The predictor length is {self.predictor_length}')  # 168

        history = TimeSeriesDataSet(
            data[lambda x: x.index <= cutoff],
            time_idx="time_idx",
            target="val",
            categorical_encoders={"Building": NaNLabelEncoder().fit(data.Building),
                                  "Condition": NaNLabelEncoder().fit(data.Condition)},
            group_ids=["Building"],
            static_categoricals=[
                "Building"
            ],

            time_varying_known_reals=["Temperature", "Humidity"],
            time_varying_known_categoricals=["Condition"],
            allow_missing_timesteps=True,
            time_varying_unknown_reals=["val"],
            max_encoder_length=self.context_length,
            max_prediction_length=self.predictor_length
        )

        test = TimeSeriesDataSet.from_dataset(history, data, min_prediction_idx=cutoff + 1)
        batch_size = 128
        test_dataloader = test.to_dataloader(train=False, batch_size=batch_size, num_workers=0,
                                             batch_sampler='synchronized')

        predictions = self.model.predict(test_dataloader)
        pred_dict = {}
        for idx in range(len(self.building_series)):
            pred_dict[self.building_series[idx]] = predictions[idx].tolist()

        save_folder_path = "../data/test"
        if not os.path.exists(save_folder_path):
            os.mkdir(save_folder_path)

        with open(f"{save_folder_path}/prediction.json", "w") as f:
            json.dump(pred_dict, f)

        return f"{save_folder_path}/prediction.json"