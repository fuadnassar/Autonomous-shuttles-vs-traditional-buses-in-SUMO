import pandas as pd
import numpy as np
import os

class TripDistributor:
    def __init__(self, input_file="Data_From_Step_3.xlsx"):
        # Load the data
        if input_file.endswith('.xlsx'):
            self.df = pd.read_excel(input_file)
        else:
            self.df = pd.read_csv(input_file)
        
        # Define proportions
        area_local = 7825.4 # the ground area for building exist in local center | Gravity approch 
        area_district = 22925.227 # the ground area for 4 building in district center | Gravity approch 
        total_area = area_local + area_district
        
        self.prop_local = area_local / total_area
        self.prop_district = area_district / total_area
        
        # Column definitions
        self.name_col = self.df.columns[0]
        self.total_col = self.df.columns[1]  # The 'agents' column
        self.hour_cols = self.df.columns[2:] # The hourly columns

    def distribute_integers(self, target_total, weights):
        """
        Distributes a target integer total across bins defined by weights 
        using the Largest Remainder Method (Hamilton method).
        """
        target_total = int(round(target_total))
        
        # Handle edge case where total is 0
        if target_total == 0:
            return np.zeros(len(weights), dtype=int)
            
        weights = weights.astype(float)
        weight_sum = weights.sum()
        
        # If weights are all 0 but we have a total to distribute, 
        # we can't distribute proportionally. Return zeros (or handle as error).
        if weight_sum == 0:
            return np.zeros(len(weights), dtype=int)
            
        # 1. Scale weights to sum to the target_total
        scaled = (weights / weight_sum) * target_total
        
        # 2. Floor to get initial integer allocation
        ints = np.floor(scaled).astype(int)
        
        # 3. Calculate the missing remainder
        remainder = target_total - ints.sum()
        
        # 4. Distribute remainder to the bins with the highest fractional parts
        if remainder > 0:
            fractions = scaled - ints
            # Get indices sorted by fraction descending
            order = np.argsort(fractions)[::-1]
            # Add 1 to the top 'remainder' bins
            ints[order[:remainder]] += 1
            
        return ints

    def process_and_save(self):
        # Create copies for output
        local_df = self.df.copy()
        district_df = self.df.copy()
        
        # Iterate over every row to calculate splits based on the row's Total
        for index, row in self.df.iterrows():
            # Get the total agents for this block (e.g., 59)
            original_total = row[self.total_col]
            if pd.isna(original_total):
                original_total = 0
            
            # Round original total to nearest integer to define our "pie"
            N = int(round(original_total))
            
            # Calculate how many go to Local vs District
            # e.g., 59 * 0.12 = 7.3 -> 7
            n_local = int(round(N * self.prop_local))
            # District gets the rest to ensure Sum = N
            n_district = N - n_local
            
            # Get the hourly weights (the shape of the traffic)
            weights = row[self.hour_cols].values
            # Handle NaNs in weights
            weights = np.nan_to_num(weights)
            
            # Distribute the calculated totals across the hours
            local_hourly_trips = self.distribute_integers(n_local, weights)
            district_hourly_trips = self.distribute_integers(n_district, weights)
            
            # Assign back to the dataframes
            local_df.loc[index, self.hour_cols] = local_hourly_trips
            district_df.loc[index, self.hour_cols] = district_hourly_trips
            
            # Update the total column to match the new sum of hours
            local_df.loc[index, self.total_col] = n_local
            district_df.loc[index, self.total_col] = n_district

        # Define output paths
        output_dir = "results"
        os.makedirs(output_dir, exist_ok=True)
        
        local_path = os.path.join(output_dir, "trips_local_center.xlsx")
        district_path = os.path.join(output_dir, "trips_district_center.xlsx")

        # Save to Excel
        local_df.to_excel(local_path, index=False)
        district_df.to_excel(district_path, index=False)
        
        print(f"Distribution complete.")
        print(f"- Local Center saved to: {local_path}")
        print(f"- District Center saved to: {district_path}")

if __name__ == "__main__":
    distributor = TripDistributor("Data_From_Step_3.xlsx")
    distributor.process_and_save()