import os.path

from utils import dataset_generator
import datetime
import pandas as pd


def main():
    train_path = "../data/train"
    if not os.path.exists(train_path):
        os.makedirs(train_path)

    weather_path = "../data/weather"
    electricity_path = "../data/electricity"
    whole_weather_path = "../data/weather/history/history_weather_vc.csv"

    generator = dataset_generator(weather_path, electricity_path)
    # generate the dataset from 20221015 to 20230308
    buildings = ['1A', '1B', '1C', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
    start_date = datetime.datetime.strptime("20210201", "%Y%m%d").date()
    end_date = datetime.datetime.strptime("20220901", "%Y%m%d").date()
    train_df_list = generator.generate_dataset(buildings, start_date, end_date, whole_weather_path, start_idx=1,
                                               weather_stride=1)
    train_df = pd.concat(train_df_list)
    train_path = "../data/train/train_buildings.csv"
    train_df = train_df.fillna(method="ffill")
    train_df.to_csv(train_path, index=False)

    return None


if __name__ == "__main__":
    main()
