import streamlit as st
import pandas as pd
import io
import os
import math
from backend12 import process_single_file

def main():

    st.set_page_config(
        layout="wide",
        page_title="Engineering Drawing Parameter Extractor",
        page_icon="⚙️",
        initial_sidebar_state="collapsed"
    )

    # --- Sidebar and Mode Selection ---
    mode = st.sidebar.radio(
        "Select run mode",
        ("Interactive Upload", "Batch‑from‑Folder"),
        help="Interactive: choose files manually. Batch: pick a folder and process everything inside."
    )
    st.sidebar.markdown("---")

    # --- CSS for styling and the results table ---
    # Comments have been added to explain what each style does.
    st.markdown("""
        <style>
        /* --- Main Header Banner --- */
        .main-header {
            text-align: center;                         /* Center the text inside */
            padding: 2rem 0;                            /* Add padding (2rem top/bottom, 0 left/right) */
            background: linear-gradient(90deg, #1e3c72 0%, #104cb5 100%); /* Blue gradient background */
            color: white;                               /* Set the text color to white */
            border-radius: 10px;                        /* Round the corners */
            margin-bottom: 2rem;                        /* Add space below the header */
        }

        /* --- Feature Boxes (under the header) --- */
        .feature-box {
            background: #1a1c23;                        /* Dark background color */
            padding: 1.5rem;                            /* Add padding inside the box */
            border-radius: 8px;                         /* Round the corners */
            border-left: 4px solid #bd0000;             /* Add a red accent line on the left */
            margin: 1rem 0;                             /* Add space above and below the box */
            height: 100%;                               /* Make all boxes in a row the same height */
        }

        /* --- Generic Stat Box (not used in current layout but available) --- */
        .stat-box {
            text-align: center;                         /* Center text */
            padding: 1rem;                              /* Add padding */
            background: white;                          /* White background */
            border-radius: 8px;                         /* Rounded corners */
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);      /* Add a subtle shadow */
            min-width: 120px;                           /* Set a minimum width */
        }

        /* --- Success and Error Message Boxes --- */
        .success-box, .error-box {
            padding: 1rem;                              /* Add padding */
            border-radius: 8px;                         /* Rounded corners */
            margin: 1rem 0;                             /* Add space above and below */
        }
        .success-box {
            background: #1a1c23;                        /* Light green background */
            color: #949ba1;                             /* Dark green text color */
            border: 1px solid #c3e6cb;                  /* Green border */
        }
        .error-box {
            background: #f8d7da;                        /* Light red background */
            color: #721c24;                             /* Dark red text color */
            border: 1px solid #f5c6cb;                  /* Red border */
        }
        
        /* --- Footer --- */
        .footer {
            text-align: center;                         /* Center the text */
            padding: 2rem 0;                            /* Add padding top/bottom */
            color: #6c757d;                             /* Grey text color */
            border-top: 1px solid #dee2e6;              /* Add a line at the top */
            margin-top: 3rem;                           /* Add space above the footer */
        }

        /* --- Results Table --- */
        .results-table-container {
            font-family: 'Courier New', Courier, monospace; /* Use a monospace font for code-like feel */
            background-color: #0E1117;                  /* Dark background matching Streamlit's dark theme */
            padding: 1rem;                              /* Padding inside the container */
            border-radius: 0.5rem;                      /* Rounded corners */
            color: #FAFAFA;                             /* Light text color */
            font-size: 0.9rem;                          /* Slightly smaller font size */
        }
        .results-table-container table {
            width: auto;                                /* Table takes up only as much width as needed */
            border-collapse: collapse;                  /* Collapse borders between cells */
        }
        .results-table-container th, .results-table-container td {
            text-align: left;                           /* Align text to the left */
            vertical-align: top;                        /* Align content to the top of the cell */
            padding: 6px 10px;                          /* Padding within each cell */
            border-right: 1px solid #4A4A4A;            /* Add a vertical separator line between columns */
        }
        .results-table-container th:last-child, .results-table-container td:last-child {
            border-right: none;                         /* Remove the separator from the last column */
        }
        .results-table-container thead tr {
            border-bottom: 1px solid #4A4A4A;           /* Add a horizontal line below the header row */
        }
        .results-table-container .header {
            color: #FF4B4B;                             /* Red color for header text (th) */
            font-weight: bold;                          /* Make header text bold */
        }
        .results-table-container .highlight {
            color: #FF4B4B;                             /* Red color for highlighted parameter names */
        }

        /* --- Status Text Area with Spinner --- */
        .status-text {
            background-color: #1a1c23;                  /* Dark background */
            color: #d1d5db;                             /* Soft white text color */
            font-family: 'SF Mono', 'Consolas', monospace; /* Use a code-style font */
            padding: 1rem 1.5rem;                       /* Add padding */
            border-radius: 8px;                         /* Rounded corners */
            border: 1px solid #333644;                  /* Subtle border */
            margin-bottom: 1rem;                        /* Space below the element */
            display: flex;                              /* Use flexbox for alignment */
            align-items: center;                        /* Vertically center the spinner and text */
            gap: 1rem;                                  /* Add space between the spinner and the text */
        }

        /* --- Animated Spinner --- */
        .spinner {
            width: 24px;                                /* Spinner width */
            height: 24px;                               /* Spinner height */
            border: 3px solid #333644;                  /* The track of the spinner */
            border-top-color: #3b82f6;                  /* The moving part of the spinner (blue) */
            border-radius: 50%;                         /* Makes it a circle */
            animation: spin 1s linear infinite;         /* The animation name, duration, and loop */
        }

        /* --- Keyframes for the Spinner Animation --- */
        @keyframes spin {
            to {
                transform: rotate(360deg);              /* Rotate a full 360 degrees */
            }
        }
        </style>
    """, unsafe_allow_html=True)

    logo_col, title_col = st.columns([1, 5]) # Ratio of column sizes

    with logo_col:
        # You can customize the size by changing the `width` value.
        st.image("jswlogo.png", width=160)

    with title_col:
        st.markdown("""
            <h1 style='margin-top: 10px; margin-bottom: 0;'>Engineering Drawing Parameter Extractor - MPPG</h1>
            <p style='font-size: 1.2rem; opacity: 0.8;'>
                Template: CYLINDER,HYD/PNUEMATIC
            </p>
        """, unsafe_allow_html=True)

    # --- File handling logic ---
    batch_dir = None
    run_batch = False
    if mode == "Batch‑from‑Folder":
        batch_dir = st.sidebar.text_input(
            "Folder path containing drawings", help="Provide the absolute path to your folder of PDF or image files."
        )
        run_batch = st.sidebar.button("Run batch processing")

    file_objs = []
    if mode == "Interactive Upload":
        uploaded_files = st.file_uploader(
            "Upload Your Engineering Drawings", type=["pdf", "png", "jpg", "jpeg"],
            accept_multiple_files=True, label_visibility="visible"
        )
        file_objs = uploaded_files or []
    elif run_batch and batch_dir:
        try:
            if os.path.isdir(batch_dir):
                files_to_process = [f for f in os.listdir(batch_dir) if f.lower().endswith((".pdf", ".png", ".jpg", ".jpeg"))]
                if files_to_process:
                    for fn in files_to_process:
                        path = os.path.join(batch_dir, fn)
                        with open(path, "rb") as f:
                            data = f.read()
                        file_objs.append(type("UploadedFile", (), {"name": fn, "read": lambda d=data: d})())
                    st.success(f"Loaded {len(file_objs)} files from the folder.")
                else:
                    st.warning("No supported files found in the folder.")
            else:
                st.error("The provided path is not a valid directory.")
        except Exception as e:
            st.error(f" Could not load files: {e}")

    # --- Main processing and display logic ---
    if file_objs:
        total_files = len(file_objs)
        st.markdown("### Processing Status...")
        progress_bar = st.progress(0)
        status_text_area = st.empty() # Placeholder for our detailed status
        all_extracted_data = []

        for i, uploaded_file in enumerate(file_objs):

            for update in process_single_file(uploaded_file.read()):
                
                # --- Update UI based on the yielded message from the backend ---
                if "status" in update:
                    # This is a progress update.
                    current_progress = (i + update.get("progress", 0)) / total_files
                    status_message = f"""
                    <div class="status-text">
                        <div class="spinner"></div>
                        <div>
                            <strong>{update['status']}</strong><br>
                            File: <code>{uploaded_file.name}</code> ({i+1}/{total_files})
                        </div>
                    </div>
                    """
                    status_text_area.markdown(status_message, unsafe_allow_html=True)
                    progress_bar.progress(current_progress)

                elif "final_result" in update:
                    # The backend finished this file and sent the final data.
                    result = update["final_result"]
                    all_extracted_data.append({
                        "filename": uploaded_file.name,
                        "data": result.get("data", {}),
                        "image": result.get("image"),
                        "reasoning": result.get("reasoning", {})
                    })

                elif "error" in update:
                    # The backend encountered an error with this file.
                    all_extracted_data.append({
                        "filename": uploaded_file.name,
                        "data": {"error": update["error"]},
                        "image": None
                    })
                    break # Stop processing this file and move to the next

        status_text_area.markdown(f'<div class="success-box"><strong>All {total_files} files processed</strong></div>', unsafe_allow_html=True)
        progress_bar.progress(1.0)
        
        if all_extracted_data:
            st.markdown("---")
            st.markdown("## Extracted Parameter Results")
            highlight_params = [p.upper() for p in ["Cylinder Action", "Bore Diameter", "Rod Diameter", "Stroke Length", "Close Length", "Operating Pressure", "Operating Temperature", "Mounting", "Rod End", "Fluid", "Drawing Number"]]
            flattened_data_for_csv = []
            
            for item in all_extracted_data:
                filename = item.get("filename", "unknown file")
                data = item.get("data", {})
                image_bytes = item.get("image", None)
                reasoning = item.get("reasoning")

                st.markdown(f"### Analysis Results: `{filename}`")
                img_col, results_col = st.columns([1, 1.2])
                
                with img_col:
                    if image_bytes:
                        st.image(image_bytes, caption=f"Analyzed Image: {filename}", use_column_width=True)
                    else:
                        st.info("No image to display for this item.")
                
                with results_col:
                    if "error" in data:
                        st.error(f"Processing Error: {data['error']}")
                    elif data:
                        # 1. Define simpler table headers for just two columns.
                        html_table = "<table><thead><tr>"
                        html_table += '<th class="header">Parameter</th><th class="header">Value</th>'
                        html_table += "</tr></thead><tbody>"

                        # 2. Loop through every parameter and create one row for each.
                        for key, val in data.items():
                            html_table += "<tr>"
                            
                            # Get the parameter name and check if it should be highlighted
                            p_name = str(key).replace("_", " ").title()
                            p_class = "highlight" if p_name.upper() in highlight_params else ""
                            
                            # Add the two cells for the parameter and its value
                            html_table += f'<td class="{p_class}">{p_name}</td>'
                            html_table += f'<td>{val}</td>'
                            
                            html_table += "</tr>"

                        html_table += "</tbody></table>"
                        st.markdown(f'<div class="results-table-container">{html_table}</div>', unsafe_allow_html=True)
                    else:
                        st.info("No parameters were extracted.")

                if reasoning:
                    with st.expander("🤖 View AI Reasoning Details"):
                        st.markdown("#### Batch 1: Core Parameters")
                        if reasoning.get("extract_batch1"):
                            st.text_area("Extraction Reasoning (Batch 1)", reasoning["extract_batch1"], height=150, key=f"re1_{filename}")
                        if reasoning.get("validate_batch1"):
                            st.text_area("Validation Reasoning (Batch 1)", reasoning["validate_batch1"], height=150, key=f"rv1_{filename}")

                        st.markdown("#### Batch 2: Secondary Parameters")
                        if reasoning.get("extract_batch2"):
                            st.text_area("Extraction Reasoning (Batch 2)", reasoning["extract_batch2"], height=150, key=f"re2_{filename}")
                        if reasoning.get("validate_batch2"):
                            st.text_area("Validation Reasoning (Batch 2)", reasoning["validate_batch2"], height=150, key=f"rv2_{filename}")

                        st.markdown("#### Batch 3: Optional Parameters")
                        if reasoning.get("extract_batch3"):
                            st.text_area("Extraction Reasoning (Batch 3)", reasoning["extract_batch3"], height=150, key=f"re3_{filename}")
                        if reasoning.get("validate_batch3"):
                            st.text_area("Validation Reasoning (Batch 3)", reasoning["validate_batch3"], height=150, key=f"rv3_{filename}")

                st.markdown("---")
            
            st.markdown("### Export Full Report")
            if all_extracted_data:
                processed_filenames = [item.get("filename", "unknown file") for item in all_extracted_data]

                long_format_data = []
                all_params_in_order = []
                for item in all_extracted_data:
                    filename = item.get("filename", "unknown file")
                    data = item.get("data", {})

                    if "error" in data:
                        long_format_data.append({"Filename": filename, "Parameter": "Processing Error", "Value": data["error"]})
                        if "Processing Error" not in all_params_in_order:
                            all_params_in_order.append("Processing Error")
                    elif data:
                        for key, value in data.items():
                            param_name = str(key).replace("_", " ").title()
                            long_format_data.append({"Filename": filename, "Parameter": param_name, "Value": value})
                            if param_name not in all_params_in_order:
                                all_params_in_order.append(param_name)
                
                if long_format_data:
                    df_long = pd.DataFrame(long_format_data)
                    df_long['Parameter'] = pd.Categorical(df_long['Parameter'], categories=all_params_in_order, ordered=True)

                    df_pivoted = df_long.pivot(index='Parameter', columns='Filename', values='Value').fillna('')
                    df_pivoted = df_pivoted[processed_filenames]
                    df_pivoted = df_pivoted.reset_index()
                    output = io.BytesIO()

                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_pivoted.to_excel(writer, index=False, sheet_name='Report')

                        workbook  = writer.book
                        worksheet = writer.sheets['Report']

                        bold_format = workbook.add_format({'bold': True})

                        for row_num in range(len(df_pivoted)):
                            worksheet.write(row_num + 1, 0, df_pivoted.iloc[row_num, 0], bold_format)

                        for idx, col in enumerate(df_pivoted):
                            series = df_pivoted[col]
                            max_len = max((
                                series.astype(str).map(len).max(),
                                len(str(series.name))
                            )) + 3 
                            
                            worksheet.set_column(idx, idx, max_len)

                    excel_data = output.getvalue()
                    st.download_button(
                        label="📄 Download Report as Excel",
                        data=excel_data,
                        file_name="engineering_parameters_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.info("No data available to generate a report.")
    
    else:
        if mode == "Batch‑from‑Folder" and not run_batch:
            st.info("Provide a folder path and click ' Run batch processing' to begin.")
        else:
            st.info("Upload files to begin analysis.")


if __name__ == "__main__":
    main()