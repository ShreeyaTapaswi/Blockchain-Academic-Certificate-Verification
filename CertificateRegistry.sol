// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @author 31474 - Shreeya Tapaswi
/// @title CertificateRegistry
/// @notice On-chain registry of academic certificate hashes. Only authorised
///         institutions can issue or revoke; anyone can verify.
contract CertificateRegistry {
    address public admin;

    struct Certificate {
        address issuer;
        uint256 issuedAt;
        bool revoked;
    }

    mapping(address => bool) public authorisedIssuers;
    mapping(bytes32 => Certificate) private certificates;

    event IssuerAuthorised(address indexed issuer);
    event IssuerRemoved(address indexed issuer);
    event CertificateIssued(bytes32 indexed certHash, address indexed issuer);
    event CertificateRevoked(bytes32 indexed certHash, address indexed issuer);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin");
        _;
    }

    modifier onlyIssuer() {
        require(authorisedIssuers[msg.sender], "Not an authorised issuer");
        _;
    }

    constructor() {
        admin = msg.sender;
    }

    function authoriseIssuer(address issuer) external onlyAdmin {
        authorisedIssuers[issuer] = true;
        emit IssuerAuthorised(issuer);
    }

    function removeIssuer(address issuer) external onlyAdmin {
        authorisedIssuers[issuer] = false;
        emit IssuerRemoved(issuer);
    }

    function issueCertificate(bytes32 certHash) external onlyIssuer {
        require(certificates[certHash].issuedAt == 0, "Already issued");
        certificates[certHash] = Certificate(msg.sender, block.timestamp, false);
        emit CertificateIssued(certHash, msg.sender);
    }

    function revokeCertificate(bytes32 certHash) external onlyIssuer {
        Certificate storage c = certificates[certHash];
        require(c.issuedAt != 0, "Not found");
        require(c.issuer == msg.sender, "Only issuing institution");
        require(!c.revoked, "Already revoked");
        c.revoked = true;
        emit CertificateRevoked(certHash, msg.sender);
    }

    function verifyCertificate(bytes32 certHash)
        external
        view
        returns (bool exists, bool valid, address issuer, uint256 issuedAt)
    {
        Certificate memory c = certificates[certHash];
        exists = c.issuedAt != 0;
        valid = exists && !c.revoked;
        issuer = c.issuer;
        issuedAt = c.issuedAt;
    }
}
