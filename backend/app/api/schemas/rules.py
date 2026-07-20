from pydantic import BaseModel


class RulesResponse(BaseModel):
    rules: list[dict]


class VpnTunnelsResponse(BaseModel):
    vpn_tunnels: list[dict]
