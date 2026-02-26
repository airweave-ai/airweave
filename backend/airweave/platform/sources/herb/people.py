"""HERB People source — syncs employees and customers from the HERB benchmark dataset."""

import json
import os
from typing import Any, AsyncGenerator, Dict, Optional, Union

from airweave.platform.configs.auth import HerbAuthConfig
from airweave.platform.configs.config import HerbConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.herb_people import HerbCustomerEntity, HerbEmployeeEntity
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="HERB People",
    short_name="herb_people",
    auth_methods=[AuthenticationMethod.DIRECT],
    auth_config_class=HerbAuthConfig,
    config_class=HerbConfig,
    labels=["Benchmark", "HERB"],
    internal=True,
)
class HerbPeopleSource(BaseSource):
    """Source that syncs employee and customer records from the HERB benchmark dataset."""

    def __init__(self):
        """Initialize the HERB people source."""
        super().__init__()
        self.data_dir: str = ""

    @classmethod
    async def create(
        cls,
        credentials: Optional[Union[Dict[str, Any], HerbAuthConfig]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HerbPeopleSource":
        """Create a new HERB people source instance."""
        instance = cls()
        if config:
            instance.data_dir = (
                config.get("data_dir", "") if isinstance(config, dict) else config.data_dir
            )
        return instance

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate employee and customer entities from HERB metadata files."""
        metadata_dir = os.path.join(self.data_dir, "metadata")

        # Employees
        emp_path = os.path.join(metadata_dir, "employee.json")
        if os.path.exists(emp_path):
            with open(emp_path) as f:
                employees = json.load(f)

            for eid, emp in employees.items():
                org = emp.get("org", "unknown")
                yield HerbEmployeeEntity(
                    employee_id=eid,
                    name=emp.get("name", ""),
                    role=emp.get("role", ""),
                    location=emp.get("location", ""),
                    org=org,
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=org,
                            name=org,
                            entity_type="HerbOrg",
                        ),
                    ],
                )

        # Customers
        cust_path = os.path.join(metadata_dir, "customers_data.json")
        if os.path.exists(cust_path):
            with open(cust_path) as f:
                customers = json.load(f)

            for cust in customers:
                company = cust.get("company", "unknown")
                yield HerbCustomerEntity(
                    customer_id=cust["id"],
                    name=cust.get("name", ""),
                    role=cust.get("role", ""),
                    company=company,
                    breadcrumbs=[
                        Breadcrumb(
                            entity_id=company,
                            name=company,
                            entity_type="HerbCompany",
                        ),
                    ],
                )

    async def validate(self) -> bool:
        """Validate that the HERB metadata directory exists."""
        metadata_dir = os.path.join(self.data_dir, "metadata")
        return os.path.isdir(metadata_dir) and os.path.exists(
            os.path.join(metadata_dir, "employee.json")
        )
