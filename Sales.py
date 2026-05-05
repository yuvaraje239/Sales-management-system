import mysql.connector
import streamlit as st
import pandas as pd

# --- Database connection ---
connection = mysql.connector.connect(
    host="localhost",
    database="project1",
    user="root",
    password=""
)
mycursor = connection.cursor(buffered=True)

# --- Session State Setup ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None
if "branch_id" not in st.session_state:
    st.session_state.branch_id = None

# --- Logout Function ---
def logout():
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.branch_id = None
    st.rerun()

# --- Routing ---
if not st.session_state.logged_in:
    st.title("Welcome 🤝")
    st.header("Login Page")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        mycursor.execute(
            "SELECT Role, branch_id FROM project1.users WHERE username=%s AND password=%s",
            (username, password)
        )
        result = mycursor.fetchone()

        if result:
            st.session_state.role, st.session_state.branch_id = result
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid username or password")

# --- Admin Page ---
elif st.session_state.role == "Admin":
    st.title("Admin Dashboard")
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Admin Overview 📈", "Add Customer ➕", "Add Payment Split 💰", "FAQ Queries"]
    )
    with tab1:
        st.subheader("Branch-specific customer sales")

        # Filters
        st.write("**Filter:**")
        mycursor.execute("SELECT DISTINCT product_name FROM project1.customer_sales")
        product_names = [row[0] for row in mycursor.fetchall()]
        mycursor.execute("SELECT DISTINCT status FROM project1.customer_sales")
        statuses = [row[0] for row in mycursor.fetchall()]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            selected_products = st.multiselect("Product", product_names)
        with col2:
            selected_statuses = st.multiselect("Status", statuses)
        with col3:
            start_date = st.date_input("Start Date", value = None)
        with col4:
            end_date = st.date_input("End Date", value = None)

        # Base query with branch restriction
        query = """
            SELECT cs.*, b.branch_name
            FROM project1.customer_sales cs
            JOIN project1.branches b ON cs.branch_id = b.branch_id
            WHERE cs.branch_id=%s
        """
        conditions, params = [], [st.session_state.branch_id]

        if selected_products:
            conditions.append(
                "cs.product_name IN ({})".format(",".join(["%s"] * len(selected_products)))
            )
            params.extend(selected_products)
        if selected_statuses:
            conditions.append(
                "cs.status IN ({})".format(",".join(["%s"] * len(selected_statuses)))
            )
            params.extend(selected_statuses)
        if start_date and end_date:
            conditions.append("cs.date BETWEEN %s AND %s")
            params.extend([start_date, end_date])
        elif start_date:
            conditions.append("cs.date >= %s")
            params.append(start_date)
        elif end_date:
            conditions.append("cs.date <= %s")
            params.append(end_date)

        if conditions:
            query += " AND " + " AND ".join(conditions)

        mycursor.execute(query, tuple(params))
        customer_sales = mycursor.fetchall()
        col_names = [desc[0] for desc in mycursor.description]
        df = pd.DataFrame(customer_sales, columns=col_names)
        
        st.divider()
        st.write("**Overview:**")

        # --- Summary Totals ---
        total_gross = df["gross_sales"].sum() if "gross_sales" in df.columns else 0
        total_received = df["received_amount"].sum() if "received_amount" in df.columns else 0
        total_pending = df["pending_amount"].sum() if "pending_amount" in df.columns else 0

        colA, colB, colC = st.columns(3)
        with colA:
            st.markdown(
                f"**Total Gross Sales**<br><span style='color:blue; font-size:20px;'>{total_gross:,.2f}</span>",
                unsafe_allow_html=True,
            )
        with colB:
            st.markdown(
                f"**Total Received Amount**<br><span style='color:green; font-size:20px;'>{total_received:,.2f}</span>",
                unsafe_allow_html=True,
            )
        with colC:
            st.markdown(
                f"**Total Pending Amount**<br><span style='color:red; font-size:20px;'>{total_pending:,.2f}</span>",
                unsafe_allow_html=True,
            )
        st.divider()
        st.write("**Monthly Wise Sale:**")
        # --- Monthly Gross vs Received vs Pending Line Chart ---
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["year_month"] = df["date"].dt.to_period("M")

            monthly_summary = (
                df.groupby("year_month")[["gross_sales", "received_amount", "pending_amount"]]
                .sum()
                .reset_index()
            )
            monthly_summary["year_month"] = monthly_summary["year_month"].astype(str)

            import altair as alt

            chart = (
                alt.Chart(monthly_summary)
                .transform_fold(
                    ["gross_sales", "received_amount", "pending_amount"],
                    as_=["Type", "Value"],
                )
                .mark_line(point=True)
                .encode(
                    x=alt.X("year_month:N", title="Month"),
                    y=alt.Y("Value:Q", title="Amount"),
                    color=alt.Color(
                        "Type:N",
                        scale=alt.Scale(
                            domain=["gross_sales", "received_amount", "pending_amount"],
                            range=["blue", "green", "red"],
                        ),
                        legend=alt.Legend(title="Amount Type"),
                    ),
                    tooltip=[
                        alt.Tooltip("year_month:N", title="Month"),
                        alt.Tooltip("Type:N", title="Type"),
                        alt.Tooltip("Value:Q", title="Amount"),
                    ],
                )
                .properties(width=700)
            )

            st.altair_chart(chart, use_container_width=True)
        st.divider()
        st.write("**Sale Table:**")
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        if "year_month" in df.columns:
            df = df.drop(columns=["year_month"])
        st.dataframe(df.reset_index(drop=True), use_container_width=True)

    with tab2:
        # --- Add Customer Sale Form ---
        st.subheader("Add New Customer Sale")
        with st.form("admin_add_sale"):
            customer_name = st.text_input("Customer Name")
            mobile_number = st.text_input("Mobile Number")
            product_name = st.text_input("Product Name")
            status = st.selectbox("Status", ["Open", "Close"])
            gross_sales = st.number_input("Gross Sales", step=5000)
            sale_date = st.date_input("Sale Date")

            submitted = st.form_submit_button("Add New Customer Data")
            if submitted:
                received_amount = 0.0
                pending_amount = gross_sales - received_amount
                try:
                    mycursor.execute("""
                        INSERT INTO project1.customer_sales 
                        (branch_id, Name, mobile_number, product_name, status, gross_sales, received_amount, pending_amount, date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        st.session_state.branch_id,
                        customer_name,
                        mobile_number,
                        product_name,
                        status,
                        gross_sales,
                        received_amount,
                        pending_amount,
                        sale_date
                    ))
                    connection.commit()
                    st.success("Customer sale added successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab3:
        # --- Add Payment Split Form ---
        st.subheader("Add Payment Split")
        with st.form("admin_add_payment"):
            mycursor.execute("SELECT sale_id, name, product_name FROM project1.customer_sales WHERE branch_id=%s",
                            (st.session_state.branch_id,))
            sales = mycursor.fetchall()
            sale_dict = {str(s[0]): f"{s[1]} - {s[2]} (ID: {s[0]})" for s in sales}

            sale_choice = st.selectbox("Select Sale", options=list(sale_dict.keys()), format_func=lambda x: sale_dict[x])
            amount_paid = st.number_input("Amount Paid", step=5000)
            payment_date = st.date_input("Payment Date")
            payment_method = st.selectbox("Payment Method", ["Cash", "Card", "UPI", "Bank Transfer"])

            submitted = st.form_submit_button("Add Payment Split")
            if submitted:
                try:
                    mycursor.execute("""
                        INSERT INTO project1.payment_splits (sale_id, payment_date, amount_paid, payment_method)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        int(sale_choice),
                        payment_date.strftime("%Y-%m-%d"),
                        amount_paid,
                        payment_method
                    ))
                    connection.commit()
                    st.success("Payment split added successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")            

    with tab4:
        st.subheader("FAQ Quaries")
        st.markdown("**Basic Queries**")
        options = [
                "Retrieve records from customer_sales",
                "Retrieve records from branches",
                "Retrieve records from payment_splits",
                "Display sales with status = 'Open'"]

            # Selectbox for choosing query
        choice = st.selectbox("Choose a query to run:", options)
        branch_id = st.session_state.get("branch_id")

            # Run query based on selection
        if choice == "Retrieve records from customer_sales":
            mycursor.execute("""
            SELECT cs.*, b.branch_name
            FROM project1.customer_sales cs
            JOIN project1.branches b ON cs.branch_id = b.branch_id
            WHERE cs.branch_id = %s""", (st.session_state.branch_id,))
        elif choice == "Retrieve records from branches":
            mycursor.execute("""SELECT *
            FROM project1.branches
            WHERE branch_id = %s""", (st.session_state.branch_id,))
        elif choice == "Retrieve records from payment_splits":
            mycursor.execute("""
            SELECT ps.*
            FROM payment_splits ps
            JOIN customer_sales cs ON ps.sale_id = cs.sale_id
            WHERE cs.branch_id = %s
            ORDER BY ps.payment_date ASC
            """, (branch_id,))
        elif choice == "Display sales with status = 'Open'":
            mycursor.execute("""
                SELECT *
                FROM customer_sales
                WHERE status = 'Open' AND branch_id = %s
            """, (branch_id,))
        
        # Fetch and display results
        data = mycursor.fetchall()
        col_names = [desc[0] for desc in mycursor.description]
        df = pd.DataFrame(data, columns=col_names)
        st.dataframe(df, use_container_width=True)

        st.divider()

        st.markdown("**Aggregation Queries**")
        options = [
                "Calculate the total gross sales.",
                "Calculate the total received amount.",
                "Calculate the total pending amount.",
                "Count the total number of sales.",
                "Find the average gross sales amount."
            ]

            # Selectbox for choosing query
        choice = st.selectbox("Choose a query to run:", options)
        branch_id = st.session_state.get("branch_id")

            # Run query based on selection
        if choice == "Calculate the total gross sales.":
            mycursor.execute("""
                SELECT SUM(gross_sales) AS total_gross
                FROM customer_sales
                WHERE branch_id = %s
            """, (branch_id,))
            
            result = mycursor.fetchone()
            total_gross = result[0] if result[0] is not None else 0
            st.metric("Total Gross Sales", f"{total_gross:,.2f}")
        elif choice == "Calculate the total received amount.":
            mycursor.execute("SELECT SUM(received_amount) AS total_received FROM customer_sales WHERE branch_id = %s", (branch_id,))
            result = mycursor.fetchone()
            total_received = result[0] if result[0] is not None else 0
            st.metric("Total Received Amount", f"{total_received:,.2f}")
        elif choice == "Calculate the total pending amount.":
            mycursor.execute("SELECT SUM(pending_amount) AS total_pending FROM customer_sales WHERE branch_id = %s", (branch_id,))
            result = mycursor.fetchone()
            total_pending_amount = result[0] if result[0] is not None else 0
            st.metric("Total Pending Amount", f"{total_pending_amount:,.2f}")
        elif choice == "Count the total number of sales.":
            mycursor.execute("""
                SELECT b.branch_name, COUNT(cs.sale_id) AS total_sales
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s
                GROUP BY b.branch_name
            """, (branch_id,))
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)
        elif choice == "Find the average gross sales amount.":
            mycursor.execute("SELECT AVG(gross_sales) AS avg_gross FROM customer_sales WHERE branch_id = %s", (branch_id,))
            result = mycursor.fetchone()
            avg_gross = result[0] if result[0] is not None else 0
            st.metric("Average Gross Sales", f"{avg_gross:,.2f}")
        
        st.divider()
        
        st.markdown("**Join-Based Queries**")
        options = [
            "Retrieve sales details along with the branch name.",
            "Retrieve sales details along with total payment received (using payment_splits).",
            "Show branch total gross sales (using JOIN & GROUP BY).",
            "Display sales along with payment method used.",
            "Retrieve sales along with branch admin name."
        ]

        choice = st.selectbox("Choose a query to run:", options)
        branch_id = st.session_state.get("branch_id")

        query = None
        params = (branch_id,)

        if choice == "Retrieve sales details along with the branch name.":
            query = """
                SELECT cs.*, b.branch_name
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s
            """

        elif choice == "Retrieve sales details along with total payment received (using payment_splits).":
            query = """
                SELECT 
                    cs.sale_id,
                    cs.name,
                    cs.product_name,
                    cs.gross_sales,
                    cs.status,
                    b.branch_name,
                    COALESCE(SUM(ps.amount_paid), 0) AS total_received
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                LEFT JOIN payment_splits ps ON cs.sale_id = ps.sale_id
                WHERE cs.branch_id = %s
                GROUP BY cs.sale_id, cs.name, cs.product_name, cs.gross_sales, cs.status, b.branch_name
            """

        elif choice == "Show branch total gross sales (using JOIN & GROUP BY).":
            query = """
                SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s
                GROUP BY b.branch_name
            """

        elif choice == "Display sales along with payment method used.":
            query = """
                SELECT 
                    cs.sale_id,
                    cs.name,
                    cs.product_name,
                    cs.gross_sales,
                    cs.status,
                    b.branch_name,
                    ps.payment_date,
                    ps.amount_paid,
                    ps.payment_method
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                LEFT JOIN payment_splits ps ON cs.sale_id = ps.sale_id
                WHERE cs.branch_id = %s
                ORDER BY cs.sale_id, ps.payment_date
            """

        elif choice == "Retrieve sales along with branch admin name.":
            query = """
                SELECT 
                    cs.sale_id,
                    cs.name,
                    cs.product_name,
                    cs.gross_sales,
                    cs.status,
                    b.branch_name,
                    b.branch_admin_name
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s
            """

        if query:
            mycursor.execute(query, params)
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)
        
        st.divider()

        st.markdown("**Financial Tracking Queries**")
        options = [
            "Find sales where the pending amount is greater than 5000.",
            "Retrieve top 3 highest gross sales.",
            "Find the branch highest total gross sales.",
            "Retrieve monthly sales summary (group by month & year).",
            "Calculate payment method-wise total collection (Cash / UPI / Card)."
        ]

        choice = st.selectbox("Choose a query to run:", options)
        branch_id = st.session_state.get("branch_id")

        if choice == "Find sales where the pending amount is greater than 5000.":
            mycursor.execute("""
                SELECT 
                    cs.sale_id,
                    cs.name,
                    cs.product_name,
                    cs.gross_sales,
                    cs.received_amount,
                    cs.pending_amount,
                    cs.status,
                    b.branch_name
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s AND cs.pending_amount > 5000
                ORDER BY cs.pending_amount DESC
            """, (branch_id,))
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

        elif choice == "Retrieve top 3 highest gross sales.":
            mycursor.execute("""
                SELECT 
                    cs.sale_id,
                    cs.name,
                    cs.product_name,
                    cs.gross_sales,
                    cs.status,
                    b.branch_name
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s
                ORDER BY cs.gross_sales DESC
                LIMIT 3
            """, (branch_id,))
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

        elif choice == "Find the branch highest total gross sales.":
            mycursor.execute("""
                SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE cs.branch_id = %s
                GROUP BY b.branch_name
                ORDER BY total_gross DESC
                LIMIT 1
            """, (branch_id,))
            result = mycursor.fetchone()
            if result:
                branch_name, total_gross = result
                st.metric("Top Branch (Gross Sales)", f"{branch_name}: {total_gross:,.2f}")
            else:
                st.write("No sales data available.")

        elif choice == "Retrieve monthly sales summary (group by month & year).":
            mycursor.execute("""
                SELECT 
                    YEAR(cs.date) AS year,
                    MONTH(cs.date) AS month,
                    SUM(cs.gross_sales) AS total_gross,
                    SUM(cs.received_amount) AS total_received,
                    SUM(cs.pending_amount) AS total_pending,
                    COUNT(*) AS total_sales
                FROM customer_sales cs
                WHERE cs.branch_id = %s
                GROUP BY YEAR(cs.date), MONTH(cs.date)
                ORDER BY year DESC, month DESC
            """, (branch_id,))
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

        elif choice == "Calculate payment method-wise total collection (Cash / UPI / Card).":
            mycursor.execute("""
                SELECT 
                    ps.payment_method,
                    SUM(ps.amount_paid) AS total_collection
                FROM payment_splits ps
                JOIN customer_sales cs ON ps.sale_id = cs.sale_id
                WHERE cs.branch_id = %s
                GROUP BY ps.payment_method
                ORDER BY total_collection DESC
            """, (branch_id,))
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)
    
    st.divider()

    if st.button("Logout"):
        logout()

# --- Super Admin Page ---
elif st.session_state.role == "Super Admin":
    st.title("Super Admin Dashboard")
    tab1, tab2, tab3, tab4 = st.tabs(["Super Admin Overview 📈", "Add Customer ➕", "Add Payment Split 💰","FAQ Queries"])
    with tab1:
        st.subheader("Customer Sales")

        # Filters
        st.write('**Filter:**')
        mycursor.execute("SELECT DISTINCT branch_name FROM project1.branches")
        branch_names = [row[0] for row in mycursor.fetchall()]
        mycursor.execute("SELECT DISTINCT product_name FROM project1.customer_sales")
        product_names = [row[0] for row in mycursor.fetchall()]
        mycursor.execute("SELECT DISTINCT status FROM project1.customer_sales")
        statuses = [row[0] for row in mycursor.fetchall()]

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1: selected_branches = st.multiselect("Branch", branch_names)
        with col2: selected_products = st.multiselect("Product", product_names)
        with col3: selected_statuses = st.multiselect("Status", statuses)
        with col4: start_date = st.date_input("Start Date", value = None)
        with col5: end_date = st.date_input("End Date", value = None)

        query = """
            SELECT cs.*, b.branch_name
            FROM project1.customer_sales cs
            JOIN project1.branches b ON cs.branch_id = b.branch_id
        """
        conditions, params = [], []
        if selected_branches:
            conditions.append("b.branch_name IN ({})".format(",".join(["%s"] * len(selected_branches))))
            params.extend(selected_branches)
        if selected_products:
            conditions.append("cs.product_name IN ({})".format(",".join(["%s"] * len(selected_products))))
            params.extend(selected_products)
        if selected_statuses:
            conditions.append("cs.status IN ({})".format(",".join(["%s"] * len(selected_statuses))))
            params.extend(selected_statuses)
        if start_date and end_date:
            conditions.append("cs.date BETWEEN %s AND %s")
            params.extend([start_date, end_date])
        elif start_date:
            conditions.append("cs.date >= %s")
            params.append(start_date)
        elif end_date:
            conditions.append("cs.date <= %s")
            params.append(end_date)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        mycursor.execute(query, tuple(params))
        customer_sales = mycursor.fetchall()
        col_names = [desc[0] for desc in mycursor.description]
        df = pd.DataFrame(customer_sales, columns=col_names)

        st.divider()
        st.write('**Overview:**')

        # --- Summary Totals ---
        total_gross = df['gross_sales'].sum() if 'gross_sales' in df.columns else 0
        total_received = df['received_amount'].sum() if 'received_amount' in df.columns else 0
        total_pending = df['pending_amount'].sum() if 'pending_amount' in df.columns else 0

        colA, colB, colC = st.columns(3)
        with colA:
            st.markdown(f"**Total Gross Sales**<br><span style='color:blue; font-size:20px;'>{total_gross:,.2f}</span>", unsafe_allow_html=True)
        with colB:
            st.markdown(f"**Total Received Amount**<br><span style='color:green; font-size:20px;'>{total_received:,.2f}</span>", unsafe_allow_html=True)
        with colC:
            st.markdown(f"**Total Pending Amount**<br><span style='color:red; font-size:20px;'>{total_pending:,.2f}</span>", unsafe_allow_html=True)
        st.divider()
        st.write('**Monthly Wise Sale:**')
        # --- Monthly Gross vs Received vs Pending Line Chart ---
        if not df.empty and 'date' in df.columns:
            # Convert to datetime
            df['date'] = pd.to_datetime(df['date'], errors='coerce')

            # Extract year-month
            df['year_month'] = df['date'].dt.to_period('M')

            # Aggregate by month
            monthly_summary = df.groupby('year_month')[['gross_sales','received_amount','pending_amount']].sum().reset_index()
            monthly_summary['year_month'] = monthly_summary['year_month'].astype(str)

            import altair as alt
            chart = (
                alt.Chart(monthly_summary)
                .transform_fold(
                    ['gross_sales','received_amount','pending_amount'],
                    as_=['Type','Value']
                )
                .mark_line(point=True)
                .encode(
                    x=alt.X('year_month:N', title='Month'),
                    y=alt.Y('Value:Q', title='Amount'),
                    color=alt.Color(
                        'Type:N',   # explicitly nominal
                        scale=alt.Scale(
                            domain=['gross_sales','received_amount','pending_amount'],
                            range=['blue','green','red']
                        ),
                        legend=alt.Legend(title="Amount Type")
                    ),
                    tooltip=[
                        alt.Tooltip('year_month:N', title='Month'),
                        alt.Tooltip('Type:N', title='Type'),
                        alt.Tooltip('Value:Q', title='Amount')
                    ]
                )
                .properties(width=700)
            )

            st.altair_chart(chart, use_container_width=True)
        st.divider()
        st.write('**Sale Table:**')
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        if "year_month" in df.columns:
            df = df.drop(columns=["year_month"])
        st.dataframe(df.reset_index(drop=True), use_container_width=True)

    with tab2:
        # --- Add Customer Sale Form ---
        st.subheader("Add New Customer Sale")
        mycursor.execute("SELECT branch_id, branch_name FROM project1.branches")
        branches = mycursor.fetchall()
        branch_dict = {str(b[0]): b[1] for b in branches}

        with st.form("superadmin_add_sale"):
            branch_choice = st.selectbox("Select Branch", options=list(branch_dict.keys()),
                                        format_func=lambda x: f"{branch_dict[x]} (ID: {x})")
            customer_name = st.text_input("Customer Name")
            mobile_number = st.text_input("Mobile Number")
            product_name = st.text_input("Product Name")
            status = st.selectbox("Status", ["Open", "Close"])   # ✅ Only Open/Close
            gross_sales = st.number_input("Gross Sales", step=5000)
            sale_date = st.date_input("Sale Date")

            submitted = st.form_submit_button("Add New Customer Data")
            if submitted:
                received_amount = 0
                pending_amount = gross_sales - received_amount
                try:
                    mycursor.execute("""
                        INSERT INTO project1.customer_sales 
                        (branch_id, Name, mobile_number, product_name, status, gross_sales, received_amount, pending_amount, date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        branch_choice,
                        customer_name,
                        mobile_number,
                        product_name,
                        status,
                        gross_sales,
                        received_amount,
                        pending_amount,
                        sale_date
                    ))
                    connection.commit()
                    st.success("Customer sale added successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab3:
        # --- Add Payment Split Form ---
        st.subheader("Add Payment Split")
        mycursor.execute("SELECT sale_id, name, product_name, branch_id FROM project1.customer_sales")
        sales = mycursor.fetchall()
        sale_dict = {str(s[0]): f"{s[1]} - {s[2]} (Branch {s[3]}, ID: {s[0]})" for s in sales}

        with st.form("superadmin_add_payment"):
            sale_choice = st.selectbox("Select Sale", options=list(sale_dict.keys()), format_func=lambda x: sale_dict[x])
            amount_paid = st.number_input("Amount Paid", step=5000)
            payment_date = st.date_input("Payment Date")
            payment_method = st.selectbox("Payment Method", ["Cash", "Card", "UPI", "Bank Transfer"])

            submitted = st.form_submit_button("Add Payment Split")
            if submitted:
                try:
                    mycursor.execute("""
                    INSERT INTO project1.payment_splits (sale_id, payment_date, amount_paid, payment_method)
                    VALUES (%s, %s, %s, %s)
                """, (
                        int(sale_choice),
                        payment_date.strftime("%Y-%m-%d"),
                        amount_paid,
                        payment_method
                    ))
                    connection.commit()
                    st.success("Payment split added successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab4:
        st.subheader("FAQ Queries")
        st.markdown("**Basic Queries**")
        # Define query options
        options = [
                "Retrieve all records from customer_sales",
                "Retrieve all records from branches",
                "Retrieve all records from payment_splits",
                "Display all sales with status = 'Open'",
                "Retrieve all sales belonging to Chennai branch"
            ]

            # Selectbox for choosing query
        choice = st.selectbox("Choose a query to run:", options)

            # Run query based on selection
        if choice == "Retrieve all records from customer_sales":
            mycursor.execute("SELECT * FROM customer_sales")
        elif choice == "Retrieve all records from branches":
            mycursor.execute("SELECT * FROM branches")
        elif choice == "Retrieve all records from payment_splits":
            mycursor.execute("SELECT * FROM payment_splits")
        elif choice == "Display all sales with status = 'Open'":
            mycursor.execute("SELECT * FROM customer_sales WHERE status = 'Open'")
        elif choice == "Retrieve all sales belonging to Chennai branch":
            mycursor.execute("SELECT * FROM customer_sales WHERE branch_id = 1")

        # Fetch and display results
        data = mycursor.fetchall()
        col_names = [desc[0] for desc in mycursor.description]
        df = pd.DataFrame(data, columns=col_names)
        st.dataframe(df, use_container_width=True)

        st.divider()
    
        st.markdown("**Aggregation Queries**")
        options = [
                "Calculate the total gross sales across all branches.",
                "Calculate the total received amount across all sales.",
                "Calculate the total pending amount across all sales.",
                "Count the total number of sales per branch.",
                "Find the average gross sales amount."
            ]
        choice = st.selectbox("Choose a query to run:", options)

        if choice == "Calculate the total gross sales across all branches.":
            mycursor.execute("SELECT SUM(gross_sales) AS total_gross FROM customer_sales")
            result = mycursor.fetchone()
            total_gross = result[0] if result[0] is not None else 0
            st.metric("Total Gross Sales", f"{total_gross:,.2f}")
        
        elif choice == "Calculate the total received amount across all sales.":
            mycursor.execute("SELECT SUM(received_amount) AS total_received FROM customer_sales")
            result = mycursor.fetchone()
            total_received = result[0] if result[0] is not None else 0
            st.metric("Total Received Amount", f"{total_received:,.2f}")
        
        elif choice == "Calculate the total pending amount across all sales.":
            mycursor.execute("SELECT SUM(pending_amount) AS total_pending FROM customer_sales")
            result = mycursor.fetchone()
            total_pending_amount = result[0] if result[0] is not None else 0
            st.metric("Total Pending Amount", f"{total_pending_amount:,.2f}")
        
        elif choice == "Count the total number of sales per branch.":
            mycursor.execute("SELECT b.branch_name, COUNT(cs.sale_id) AS total_sales FROM customer_sales cs JOIN branches b ON cs.branch_id = b.branch_id GROUP BY b.branch_name")
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)
        
        elif choice == "Find the average gross sales amount.":
            mycursor.execute("SELECT AVG(gross_sales) AS avg_gross FROM customer_sales")
            result = mycursor.fetchone()
            avg_gross = result[0] if result[0] is not None else 0
            st.metric("Average Gross Sales", f"{avg_gross:,.2f}")
        
        st.divider()
        
        st.markdown("**Join-Based Queries**")
        options = [
                "Retrieve sales details along with the branch name.",
                "Retrieve sales details along with total payment received (using payment_splits).",
                "Show branch-wise total gross sales (using JOIN & GROUP BY).",
                "Display sales along with payment method used.",
                "Retrieve sales along with branch admin name."
            ]

            # Selectbox for choosing query
        choice = st.selectbox("Choose a query to run:", options)

            # Run query based on selection
        if choice == "Retrieve sales details along with the branch name.":
            mycursor.execute("SELECT cs.*, b.branch_name FROM customer_sales cs JOIN branches b ON cs.branch_id = b.branch_id")
        elif choice == "Retrieve sales details along with total payment received (using payment_splits).":
            mycursor.execute("""SELECT 
                cs.sale_id,
                cs.name,
                cs.product_name,
                cs.gross_sales,
                cs.status,
                b.branch_name,
                COALESCE(SUM(ps.amount_paid), 0) AS total_received
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            LEFT JOIN payment_splits ps ON cs.sale_id = ps.sale_id
            GROUP BY cs.sale_id, cs.name, cs.product_name, cs.gross_sales, cs.status, b.branch_name""")
        elif choice == "Show branch-wise total gross sales (using JOIN & GROUP BY).":
            mycursor.execute("""
            SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            GROUP BY b.branch_name
            """)
        elif choice == "Display sales along with payment method used.":
            mycursor.execute("""
            SELECT 
                cs.sale_id,
                cs.name,
                cs.product_name,
                cs.gross_sales,
                cs.status,
                b.branch_name,
                ps.payment_date,
                ps.amount_paid,
                ps.payment_method
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            LEFT JOIN payment_splits ps ON cs.sale_id = ps.sale_id
            ORDER BY cs.sale_id, ps.payment_date
            """)
        elif choice == "Retrieve sales along with branch admin name.":
            mycursor.execute("""
            SELECT 
                cs.sale_id,
                cs.name,
                cs.product_name,
                cs.gross_sales,
                cs.status,
                b.branch_name,
                b.branch_admin_name
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            """)

        results = mycursor.fetchall()
        col_names = [desc[0] for desc in mycursor.description]
        df = pd.DataFrame(results, columns=col_names)
        st.dataframe(df, use_container_width=True)
    
        st.divider()
        
        st.markdown("**Financial Tracking Queries**")
        options = [
                "Find sales where the pending amount is greater than 5000.",
                "Retrieve top 3 highest gross sales.",
                "Find the branch with highest total gross sales.",
                "Retrieve monthly sales summary (group by month & year).",
                "Calculate payment method-wise total collection (Cash / UPI / Card)."
            ]

            # Selectbox for choosing query
        choice = st.selectbox("Choose a query to run:", options)

            # Run query based on selection
        if choice == "Find sales where the pending amount is greater than 5000.":
            mycursor.execute("""SELECT 
                cs.sale_id,
                cs.name,
                cs.product_name,
                cs.gross_sales,
                cs.received_amount,
                cs.pending_amount,
                cs.status,
                b.branch_name
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            WHERE cs.pending_amount > 5000
            ORDER BY cs.pending_amount DESC
            """)
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

        elif choice == "Retrieve top 3 highest gross sales.":
            mycursor.execute("""
            SELECT 
                cs.sale_id,
                cs.name,
                cs.product_name,
                cs.gross_sales,
                cs.status,
                b.branch_name
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            ORDER BY cs.gross_sales DESC
            LIMIT 3
            """)
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

        elif choice == "Find the branch with highest total gross sales.":
            mycursor.execute("""
            SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross
            FROM customer_sales cs
            JOIN branches b ON cs.branch_id = b.branch_id
            GROUP BY b.branch_name
            ORDER BY total_gross DESC
            LIMIT 1
            """)
            if result:
                branch_name, total_gross = result
                st.metric("Top Branch (Gross Sales)", f"{branch_name}: {total_gross:,.2f}")
            else:
                st.write("No sales data available.")

        elif choice == "Retrieve monthly sales summary (group by month & year).":
            mycursor.execute("""
            SELECT 
                YEAR(cs.date) AS year,
                MONTH(cs.date) AS month,
                SUM(cs.gross_sales) AS total_gross,
                SUM(cs.received_amount) AS total_received,
                SUM(cs.pending_amount) AS total_pending,
                COUNT(*) AS total_sales
            FROM customer_sales cs
            GROUP BY YEAR(cs.date), MONTH(cs.date)
            ORDER BY year DESC, month DESC
            """)
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

        elif choice == "Calculate payment method-wise total collection (Cash / UPI / Card).":
            mycursor.execute("""
            SELECT 
                ps.payment_method,
                SUM(ps.amount_paid) AS total_collection
            FROM payment_splits ps
            GROUP BY ps.payment_method
            ORDER BY total_collection DESC
            """)
            results = mycursor.fetchall()
            col_names = [desc[0] for desc in mycursor.description]
            df = pd.DataFrame(results, columns=col_names)
            st.dataframe(df, use_container_width=True)

    st.divider()
    
    if st.button("Logout"):
        logout()

# --- Unknown Role ---
else:
    st.error("Unknown role")
    if st.button("Logout"):
        logout()
