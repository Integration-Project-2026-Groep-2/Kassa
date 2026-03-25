from __future__ import annotations

import asyncio
import logging
import xmlrpc.client
from typing import Any, Optional


class OdooClient:
    def __init__(
        self,
        url: str,
        database: str,
        username: str,
        password: str,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.database = database
        self.username = username
        self.password = password
        self.logger = logger or logging.getLogger(__name__)

        self.uid: int | None = None
        self.common_proxy = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.object_proxy = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    async def connect(self) -> None:
        self.uid = await asyncio.to_thread(
            self.common_proxy.authenticate,
            self.database,
            self.username,
            self.password,
            {},
        )
        if not self.uid:
            raise RuntimeError("Failed to authenticate with Odoo.")
        self.logger.info("Connected to Odoo as uid=%s", self.uid)

    async def _ensure_connected(self) -> None:
        if self.uid is None:
            await self.connect()

    async def _execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        await self._ensure_connected()
        kwargs = kwargs or {}
        return await asyncio.to_thread(
            self.object_proxy.execute_kw,
            self.database,
            self.uid,
            self.password,
            model,
            method,
            args,
            kwargs,
        )

    async def _find_country_id(self, country_code: str | None) -> int | None:
        if not country_code:
            return None

        result = await self._execute_kw(
            "res.country",
            "search_read",
            [[["code", "=", country_code]]],
            {"fields": ["id"], "limit": 1},
        )
        return result[0]["id"] if result else None

    async def _search_company_by_crm_id(self, crm_id: str) -> dict[str, Any] | None:
        result = await self._execute_kw(
            "res.partner",
            "search_read",
            [[["ref", "=", crm_id], ["is_company", "=", True]]],
            {"fields": ["id", "name"], "limit": 1},
        )
        return result[0] if result else None

    async def _search_partner_by_crm_id_or_email(
        self,
        crm_id: str,
        email: str,
    ) -> dict[str, Any] | None:
        by_ref = await self._execute_kw(
            "res.partner",
            "search_read",
            [[["ref", "=", crm_id], ["is_company", "=", False]]],
            {"fields": ["id", "name", "email"], "limit": 1},
        )
        if by_ref:
            return by_ref[0]

        by_email = await self._execute_kw(
            "res.partner",
            "search_read",
            [[["email", "=", email], ["is_company", "=", False]]],
            {"fields": ["id", "name", "email"], "limit": 1},
        )
        return by_email[0] if by_email else None

    async def upsert_company(
        self,
        crm_id: str,
        vat_number: str,
        name: str,
        email: str,
        is_active: bool,
        phone: str | None = None,
        street: str | None = None,
        house_number: str | None = None,
        postal_code: str | None = None,
        city: str | None = None,
        country: str | None = None,
    ) -> int:
        existing = await self._search_company_by_crm_id(crm_id)

        country_id = await self._find_country_id(country)
        street_value = " ".join(part for part in [street, house_number] if part)

        values: dict[str, Any] = {
            "name": name,
            "is_company": True,
            "vat": vat_number,
            "email": email,
            "active": is_active,
            "ref": crm_id,
        }

        if phone:
            values["phone"] = phone
        if street_value:
            values["street"] = street_value
        if postal_code:
            values["zip"] = postal_code
        if city:
            values["city"] = city
        if country_id:
            values["country_id"] = country_id

        if existing:
            await self._execute_kw("res.partner", "write", [[existing["id"]], values])
            self.logger.info("Updated company '%s' in Odoo.", name)
            return int(existing["id"])

        company_id = await self._execute_kw("res.partner", "create", [values])
        self.logger.info("Created company '%s' in Odoo.", name)
        return int(company_id)

    async def upsert_partner(
        self,
        crm_id: str,
        email: str,
        first_name: str,
        last_name: str,
        role: str,
        is_active: bool,
        phone: str | None = None,
        badge_code: str | None = None,
        company_crm_id: str | None = None,
        street: str | None = None,
        house_number: str | None = None,
        postal_code: str | None = None,
        city: str | None = None,
        country: str | None = None,
    ) -> int:
        existing = await self._search_partner_by_crm_id_or_email(crm_id, email)

        parent_id: int | None = None
        if company_crm_id:
            company = await self._search_company_by_crm_id(company_crm_id)
            if company:
                parent_id = int(company["id"])

        country_id = await self._find_country_id(country)
        street_value = " ".join(part for part in [street, house_number] if part)

        values: dict[str, Any] = {
            "name": f"{first_name} {last_name}".strip(),
            "firstname": first_name,
            "lastname": last_name,
            "email": email,
            "active": is_active,
            "ref": crm_id,
            "is_company": False,
        }

        if phone:
            values["phone"] = phone
        if badge_code:
            values["barcode"] = badge_code
        if parent_id:
            values["parent_id"] = parent_id
        if street_value:
            values["street"] = street_value
        if postal_code:
            values["zip"] = postal_code
        if city:
            values["city"] = city
        if country_id:
            values["country_id"] = country_id

        if existing:
            await self._execute_kw("res.partner", "write", [[existing["id"]], values])
            self.logger.info("Updated partner '%s'.", values["name"])
            return int(existing["id"])

        partner_id = await self._execute_kw("res.partner", "create", [values])
        self.logger.info("Created partner '%s'.", values["name"])
        return int(partner_id)

    async def deactivate_partner_by_crm_id_or_email(self, crm_id: str, email: str) -> None:
        existing = await self._search_partner_by_crm_id_or_email(crm_id, email)
        if not existing:
            self.logger.warning("No partner found to deactivate: crm_id=%s email=%s", crm_id, email)
            return

        await self._execute_kw("res.partner", "write", [[existing["id"]], {"active": False}])
        self.logger.info("Partner deactivated in Odoo: %s", email)

    async def deactivate_company_by_crm_id(self, crm_id: str) -> None:
        existing = await self._search_company_by_crm_id(crm_id)
        if not existing:
            self.logger.warning("No company found to deactivate: crm_id=%s", crm_id)
            return

        await self._execute_kw("res.partner", "write", [[existing["id"]], {"active": False}])
        self.logger.info("Company deactivated in Odoo: crm_id=%s", crm_id)
