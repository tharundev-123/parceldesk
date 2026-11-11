# ParcelDesk — Power BI Desktop Step-by-Step Guide

Follow these click-by-click steps to build the ParcelDesk analytics report from the three CSV files in the `analytics/` folder and save it as **`parceldesk-analytics.pbix`**.

---

## Step 1: Open Power BI Desktop & Load the 3 CSV Files

1. Open **Power BI Desktop** on Windows.
2. If a welcome popup appears, close it (click the **X** in the top-right corner) or click **Blank report**.
3. Load the **first CSV (`vw_daily_parcel_volume.csv`)**:
   - In the top ribbon, go to **Home** → click **Get data** → select **Text/CSV**.
   - Browse to your `parceldesk-project/analytics/` folder, select **`vw_daily_parcel_volume.csv`**, and click **Open**.
   - In the preview window, verify that the headers (`log_date`, `hostel_name`, `total_parcels`, `collected_parcels`, `pending_parcels`) appear at the top.
   - Click **Load** at the bottom-right.
4. Repeat for the **second CSV (`vw_avg_pickup_time.csv`)**:
   - Click **Home** → **Get data** → **Text/CSV**.
   - Select **`analytics/vw_avg_pickup_time.csv`** → click **Open** → click **Load**.
5. Repeat for the **third CSV (`vw_pending_parcels.csv`)**:
   - Click **Home** → **Get data** → **Text/CSV**.
   - Select **`analytics/vw_pending_parcels.csv`** → click **Open** → click **Load**.
6. On the right-hand **Data** pane, confirm all three tables appear:
   - `vw_daily_parcel_volume`
   - `vw_avg_pickup_time`
   - `vw_pending_parcels`

> **Quick Check (Optional):** If any numeric column shows without a summation `Σ` icon or `log_date` isn't a date, click **Home** → **Transform data** to open Power Query Editor, verify data types (`log_date` = Date, counts = Whole Number, `avg_pickup_hours` & `hours_waiting` = Decimal Number), then click **Close & Apply**.

---

## Step 2: Build Chart 1 — Parcels Per Day

1. Click on an empty area in the **top-left** of the white report canvas.
2. In the **Visualizations** pane (right side), click the **Stacked column chart** icon (vertical bars).
3. In the **Data** pane, expand **`vw_daily_parcel_volume`**:
   - Drag **`log_date`** into the **X-axis** box.
     - *Tip:* Click the small downward arrow next to `log_date` inside the **X-axis** box and select **`log_date`** (instead of *Date Hierarchy*) so exact dates display cleanly.
   - Drag **`total_parcels`** into the **Y-axis** box.
   - *(Optional)* Drag **`hostel_name`** into the **Legend** box to color-code daily volume by hostel.
4. Give the chart a clear title:
   - With the chart selected, click the **Format your visual** (paintbrush) icon in the **Visualizations** pane.
   - Switch to the **General** tab → expand **Title** → change **Text** to **`Parcels Per Day`**.
   - *(Optional)* Under the **Visual** tab, turn **Data labels** **On**.

---

## Step 3: Build Chart 2 — Average Pickup Hours per Hostel

1. Click on an empty area in the **top-right** of the report canvas.
2. In the **Visualizations** pane, click the **Clustered bar chart** icon (horizontal bars).
3. In the **Data** pane, expand **`vw_avg_pickup_time`**:
   - Drag **`hostel_name`** into the **Y-axis** box.
   - Drag **`avg_pickup_hours`** into the **X-axis** box.
   - Click the small downward arrow next to `avg_pickup_hours` inside the **X-axis** box and make sure **Average** (or **Sum**) is selected.
4. Format the chart:
   - Click **Format your visual** (paintbrush) → **Visual** tab → toggle **Data labels** to **On** so exact hours (e.g., `2.00`, `0.02`) are visible.
   - Switch to **General** tab → expand **Title** → change **Text** to **`Average Pickup Hours per Hostel`**.

---

## Step 4: Build Chart 3 — Pending Parcels per Hostel

1. Click on an empty area in the **bottom** half of the report canvas.
2. In the **Visualizations** pane, click the **Clustered column chart** icon (or **Donut chart**).
3. In the **Data** pane, expand **`vw_pending_parcels`**:
   - Drag **`hostel_name`** into the **X-axis** box (or **Legend** if using a Donut chart).
   - Drag **`parcel_id`** into the **Y-axis** box (or **Values**).
   - **Important:** Click the small downward arrow next to `parcel_id` inside the **Y-axis** / **Values** box and select **Count** (or **Count (Distinct)**) — do **not** leave it as *Sum*, because `parcel_id` is an ID number!
4. Format the chart:
   - Click **Format your visual** (paintbrush) → **Visual** tab → toggle **Data labels** to **On**.
   - Switch to **General** tab → expand **Title** → change **Text** to **`Pending Parcels per Hostel`**.

---

## Step 5: Add a Title Banner & DP-900 Note (Optional)

1. In the top ribbon, click **Home** → **Text box**.
2. Drag it across the top of the page and type:  
   **`ParcelDesk — Hostel Parcel Analytics (Azure SQL + Blob Storage)`**
3. Select the text, set the font size to **20**, and make it **Bold**.
4. You can also add a small **Text box** in the bottom corner noting the DP-900 data classification:
   - *Structured Data:* Azure SQL Database (`users`, `hostels`, `students`, `parcels`, `handovers`)
   - *Semi-Structured Data:* JSON notification payloads (`notifications.payload_json`)
   - *Unstructured Data:* Parcel condition photos in Azure Blob Storage (`parcel-photos`)

---

## Step 6: Save the Power BI Report

1. Click **File** in the top-left menu → **Save as**.
2. Navigate to your project folder (`parceldesk-project/analytics/`).
3. In **File name**, enter **`parceldesk-analytics`** (it saves as **`parceldesk-analytics.pbix`**).
4. Click **Save**.

---

## Refreshing Data Later

- **From Updated CSVs:** Re-export the views into `analytics/*.csv`, open `parceldesk-analytics.pbix`, and click **Home** → **Refresh**.
- **Or Live DirectQuery / Import from Azure SQL:** In Power BI Desktop, use **Home** → **Get data** → **Azure** → **Azure SQL database**, enter your server (`parceldesk-td.database.windows.net`) and database (`parceldesk-db`), select the three views (`vw_daily_parcel_volume`, `vw_avg_pickup_time`, `vw_pending_parcels`), and load them directly.

