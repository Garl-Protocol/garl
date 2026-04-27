// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/MerkleAnchor.sol";

/**
 * @title DeployScript
 * @notice Deploy MerkleAnchor to Base (mainnet or sepolia).
 *
 * Usage:
 *   forge script contracts/script/Deploy.s.sol:DeployScript \
 *     --rpc-url https://sepolia.base.org \
 *     --private-key $DEPLOYER_PRIVATE_KEY \
 *     --broadcast
 *
 * After deploy, update backend env:
 *   GARL_MERKLE_ANCHOR_CONTRACT=<deployed_address>
 *   GARL_MERKLE_ANCHOR_CHAIN_ID=84532   # Base Sepolia
 *   # or 8453 for Base Mainnet
 *
 * Cost: ~$0.50 deploy on Base mainnet, plus ~$0.001 per anchor() call.
 * Weekly anchoring → ~$1-3/year ongoing.
 */
contract DeployScript is Script {
    function run() external returns (MerkleAnchor) {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        vm.startBroadcast(deployerKey);
        MerkleAnchor anchor = new MerkleAnchor();
        vm.stopBroadcast();
        return anchor;
    }
}
