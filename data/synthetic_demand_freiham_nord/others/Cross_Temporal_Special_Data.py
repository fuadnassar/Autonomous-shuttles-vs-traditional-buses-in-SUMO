import pandas as pd
import os

class CrossTemporalSpecialData:
    def __init__(self, input_dir='input', output_dir='results'):
        self.input_dir = input_dir
        self.output_dir = output_dir
        
        # Define file paths
        self.data_file = os.path.join(self.input_dir, 'Data_from_step_three.xlsx')
        self.dist_file = os.path.join(self.input_dir, 'Hourly_Demand_Distribution_Refind.xlsx')
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"Created directory: {self.output_dir}")

    def get_dist_type(self, col_name):
        """
        Maps the input column name to the corresponding column in the Distribution file.
        Handles the 'eduction' typo in the input file.
        """
        col_lower = col_name.lower()
        if col_lower.startswith('occupation'):
            return 'Occupation'
        elif col_lower.startswith('eduction'):  # Handling typo in source data
            return 'Education'
        elif col_lower.startswith('shopping'):
            return 'Shopping'
        elif col_lower.startswith('errands'):
            return 'Errands'
        elif col_lower.startswith('leisure'):
            return 'Leisure'
        elif col_lower.startswith('accompaniment'):
            return 'Accompaniment'
        return None

    def run(self):
        print("Loading data...")
        try:
            # Load the Excel files
            df_data = pd.read_excel(self.data_file)
            df_dist = pd.read_excel(self.dist_file)
        except FileNotFoundError as e:
            print(f"Error: Could not find file. {e}")
            return

        # Identify target columns in the data file (those that map to a distribution type)
        target_cols = [c for c in df_data.columns if self.get_dist_type(c) is not None]
        
        print(f"Found {len(target_cols)} columns to process.")

        # Process each target column
        for col in target_cols:
            dist_type = self.get_dist_type(col)
            
            # Create a dictionary for weights: {'5-6': 0.0597, ...}
            # This ensures we match the correct weight to the correct time label
            weights = dict(zip(df_dist['Display_Time'], df_dist[dist_type]))
            
            # Initialize the result DataFrame with 'name' and the original values (renamed)
            result_df = pd.DataFrame()
            
            # Use 'name' from input if available, otherwise just keep index alignment
            if 'name' in df_data.columns:
                result_df['name'] = df_data['name']
            
            # The column name in output is '{original_name}_agents'
            result_df[f'{col}_agents'] = df_data[col]
            
            # Calculate distributed values for each time slot
            # Iterating through df_dist['Display_Time'] ensures columns are in correct order (5-6, 6-7, ...)
            for time_slot in df_dist['Display_Time']:
                weight = weights.get(time_slot, 0)
                # Multiply the agent count by the weight for this hour
                result_df[time_slot] = df_data[col] * weight
            
            # Generate Output Filename
            # Capitalize the first letter (e.g., occupation_inside -> Occupation_inside)
            filename_base = col[0].upper() + col[1:]
            filename = f"{filename_base}_Temporal_Distribution.xlsx"
            filepath = os.path.join(self.output_dir, filename)
            
            # Save to Excel
            result_df.to_excel(filepath, index=False)
            print(f"Generated: {filename}")

        print("\nProcessing complete. All files saved to 'results' folder.")

if __name__ == "__main__":
    # Create the processor and run it
    processor = CrossTemporalSpecialData()
    processor.run()