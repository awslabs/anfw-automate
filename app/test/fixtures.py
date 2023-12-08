from hypothesis import strategies as st
from hypothesis_regex import regex
from hypothesis.extra.pandas import data_frames, column, indexes
import string

version = st.just("0.2.0")
vpc = st.text(alphabet=(string.ascii_lowercase+string.digits), min_size=8, max_size=17)
account = st.text(alphabet=(string.digits), min_size=12, max_size=12)
#r"(af|ap|ca|eu|me|sa|us)-(central|north|(north(?:east|west))|south|south(?:east|west)|east|west)-\d{1}$"gm 
# regions = ['ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3', 'ap-south-1', 'ap-southeast-1', 'ap-southeast-2', 'ca-central-1', 'eu-central-1', 'eu-north-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'sa-east-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']
# region = st.sampled_from(regions)
region = regex(r"(af|ap|ca|eu|me|sa|us)-(central|north|(north(?:east|west))|south|south(?:east|west)|east|west)-\d{1}$")
rule_key = ["https", "http", "tls","custom"]

org_units = [
    "Core-1",
    "Core-2",
    "Non-Business-Critical-1",
    "Non-Business-Critical-2",
    "Other-1",
    "Other-2",
]
org_units_type = ["ProdOU", "NonProdOU", "Other"]
org_units_dict = {
    "NonProdOU": ["NonBusinessCritical-1", "NonBusinessCritical-2"],
    "ProdOU": ["Core-1", "Core-2"],
    "ProdOU": ["Other-1", "Other-2"],
}

account_list = st.lists(
    st.fixed_dictionaries(
        {
            "Id": st.from_regex("[0-9]{12}", fullmatch=True),
            "Arn": st.from_regex("arn:aws:organizations:[a-z]{6}:[0-9]{12}:[a-z]{10}"),
            "Email": st.emails(),
            "Name": st.text(),
            "Status": st.sampled_from(["ACTIVE", "SUSPENDED"]),
            "JoinedMethod": st.sampled_from(["INVITED", "CREATED"]),
            "JoinedTimestamp": st.datetimes(),
            "OrgUnit": st.sampled_from(org_units),
            "projectName": st.text(),
            "OrgUnitType": st.sampled_from(org_units_type),
        },
    )
)

account_list_df = data_frames(
    columns=[
        column("AwsAccountId", st.from_regex("[0-9]{12}", fullmatch=True), dtype=str),
        column("OrgUnit", st.sampled_from(org_units), dtype=str),
        column("projectName", st.text(), dtype=str),
        column("OrgUnitType", st.sampled_from(org_units_type), dtype=str),
    ],
    index=indexes(dtype=int, min_size=2),
)

fix_threshold = st.fixed_dictionaries(
    {
        "ProdOU": st.integers(min_value=1, max_value=5),
        "NonProdOU": st.integers(min_value=1, max_value=5),
        "Other": st.integers(min_value=1, max_value=5),
    }
)
