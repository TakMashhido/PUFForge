#!/usr/bin/env python3
"""
PUF CRP Generator
Generates Challenge-Response Pairs for all PUF types using pypuf library.
Configuration via config.yml.

Supports two modes:
1. Random generation (default): Generate random challenges and get responses
2. User-provided challenges: Provide challenges (file or CLI) and get responses
"""

import argparse
import yaml
import numpy as np
import pandas as pd
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Import pypuf modules
try:
    from pypuf.simulation import (
        ArbiterPUF,
        XORArbiterPUF,
        LightweightSecurePUF,
        PermutationPUF,
        InterposePUF,
        FeedForwardArbiterPUF,
        XORFeedForwardArbiterPUF,
        BistableRingPUF,
        XORBistableRingPUF,
        RandomTransformationPUF,
    )
    from pypuf.io import random_inputs
except ImportError as e:
    print(f"Error importing pypuf: {e}")
    print("Make sure pypuf is installed: uv add pypuf")
    sys.exit(1)


def load_config(config_path: str = "config.yml") -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


def generate_bistable_weights(n: int, seed: int) -> np.ndarray:
    """Generate random weights for BistableRingPUF."""
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, size=n+1)


def generate_feedforward_connections(n: int, num_ff: int, seed: int) -> List[Tuple[int, int]]:
    """Generate feed-forward connections for FeedForwardArbiterPUF."""
    rng = np.random.default_rng(seed)
    connections = []
    for _ in range(num_ff):
        from_stage = rng.integers(0, n - 2)
        to_stage = rng.integers(from_stage + 1, n - 1)
        connections.append((int(from_stage), int(to_stage)))
    return connections


def generate_xor_feedforward_connections(n: int, k: int, num_ff: int, seed: int) -> List[List[Tuple[int, int]]]:
    """Generate feed-forward connections for XORFeedForwardArbiterPUF."""
    rng = np.random.default_rng(seed)
    all_connections = []
    for chain_idx in range(k):
        chain_connections = []
        for _ in range(num_ff):
            from_stage = rng.integers(0, n - 2)
            to_stage = rng.integers(from_stage + 1, n - 1)
            chain_connections.append((int(from_stage), int(to_stage)))
        all_connections.append(chain_connections)
    return all_connections


def create_puf_instance(puf_name: str, params: Dict[str, Any], seed: int):
    """Create a PUF instance based on type and parameters."""
    n = params.get('n', 128)
    
    if puf_name == 'arbiter_puf':
        return ArbiterPUF(n=n, seed=seed)
    elif puf_name == 'xor_arbiter_puf':
        return XORArbiterPUF(n=n, k=params.get('k', 4), seed=seed)
    elif puf_name == 'lightweight_secure_puf':
        return LightweightSecurePUF(n=n, k=params.get('k', 4), seed=seed)
    elif puf_name == 'permutation_puf':
        return PermutationPUF(n=n, k=params.get('k', 4), seed=seed)
    elif puf_name == 'interpose_puf':
        return InterposePUF(
            n=n,
            k_down=params.get('k_down', 2),
            k_up=params.get('k_up', 1),
            interpose_pos=params.get('interpose_pos', None),
            seed=seed
        )
    elif puf_name == 'feedforward_arbiter_puf':
        ff = params.get('feedforward_connections')
        if ff is None:
            num_ff = params.get('num_feedforward', 3)
            ff = generate_feedforward_connections(n, num_ff, seed)
        return FeedForwardArbiterPUF(n=n, ff=ff, seed=seed)
    elif puf_name == 'xor_feedforward_arbiter_puf':
        ff = params.get('feedforward_connections')
        if ff is None:
            num_ff = params.get('num_feedforward', 3)
            k = params.get('k', 2)
            ff = generate_xor_feedforward_connections(n, k, num_ff, seed)
        return XORFeedForwardArbiterPUF(n=n, k=params.get('k', 2), ff=ff, seed=seed)
    elif puf_name == 'bistable_ring_puf':
        weights = params.get('weights')
        if weights is None:
            weights = generate_bistable_weights(n, seed)
        else:
            weights = np.array(weights)
        return BistableRingPUF(n=n, weights=weights)
    elif puf_name == 'xor_bistable_ring_puf':
        k = params.get('k', 2)
        weights = params.get('weights')
        if weights is None:
            rng = np.random.default_rng(seed)
            weights = rng.normal(0, 1, size=(k, n+1))
        else:
            weights = np.array(weights)
        return XORBistableRingPUF(n=n, k=k, weights=weights)
    elif puf_name == 'random_transformation_puf':
        return RandomTransformationPUF(n=n, k=params.get('k', 2), seed=seed)
    else:
        raise ValueError(f"Unknown PUF type: {puf_name}")


def get_response_length(puf_params: Dict[str, Any], global_config: Dict[str, Any]) -> int:
    """Get response length from PUF params or global config, with default of 1."""
    # Per-PUF override takes precedence over global default
    return puf_params.get('response_length', global_config.get('response_length', 1))


def generate_multi_bit_response(
    puf_name: str,
    puf_params: Dict[str, Any],
    global_config: Dict[str, Any],
    challenges: np.ndarray,
    base_seed: int
) -> np.ndarray:
    """Generate multi-bit responses by creating N PUF instances with sequential seeds.
    
    Creates response_length independent PUF instances with seeds:
    base_seed, base_seed+1, ..., base_seed+response_length-1
    Evaluates each on the same challenges and concatenates 1-bit responses.
    """
    response_length = get_response_length(puf_params, global_config)
    
    if response_length <= 1:
        # Single bit response - use original logic
        puf = create_puf_instance(puf_name, puf_params, base_seed)
        responses = puf.eval(challenges)
        return responses
    
    # Multi-bit: create N instances with sequential seeds
    all_responses = []
    for i in range(response_length):
        instance_seed = base_seed + i
        puf = create_puf_instance(puf_name, puf_params, instance_seed)
        bit_responses = puf.eval(challenges)
        all_responses.append(bit_responses)
    
    # Stack responses horizontally: shape (N_challenges, response_length)
    return np.column_stack(all_responses)


def binary_string_to_challenge(challenge_str: str, n: int) -> np.ndarray:
    """Convert binary string (0/1) to pypuf challenge format (-1/1)."""
    if len(challenge_str) != n:
        raise ValueError(f"Challenge length {len(challenge_str)} != expected {n}")
    # Convert '0' -> -1, '1' -> 1
    return np.array([1 if c == '1' else -1 for c in challenge_str], dtype=np.int8)


def challenges_to_binary_strings(challenges: np.ndarray) -> List[str]:
    """Convert numpy array of challenges (-1/1) to binary strings (0/1)."""
    binary_challenges = []
    for ch in challenges:
        bits = ['1' if b == 1 else '0' for b in ch]
        binary_challenges.append(''.join(bits))
    return binary_challenges


def responses_to_binary_strings(responses: np.ndarray) -> List[str]:
    """Convert numpy array of responses (-1/1) to binary strings (0/1).
    Handles both 1D (single-bit) and 2D (multi-bit) response arrays.
    """
    binary_responses = []
    for resp in responses:
        if np.isscalar(resp):
            # Single scalar response (1-bit)
            bits = '1' if resp == 1 else '0'
        elif resp.ndim == 1:
            # 1D array (single-bit per challenge)
            bits = ''.join(['1' if b == 1 else '0' for b in resp])
        else:
            # 2D array (multi-bit per challenge) - resp is a row vector
            bits = ''.join(['1' if b == 1 else '0' for b in resp])
        binary_responses.append(bits)
    return binary_responses


def load_challenges_from_file(filepath: str, challenge_length: int) -> np.ndarray:
    """Load challenges from a CSV file. Expects a 'challenge' column with binary strings."""
    df = pd.read_csv(filepath, dtype={'challenge': str})
    
    if 'challenge' not in df.columns:
        raise ValueError("CSV must have a 'challenge' column")
    
    challenges = []
    for idx, row in df.iterrows():
        ch_str = str(row['challenge']).strip()
        if len(ch_str) != challenge_length:
            raise ValueError(f"Row {idx}: challenge length {len(ch_str)} != expected {challenge_length}")
        challenges.append(binary_string_to_challenge(ch_str, challenge_length))
    
    return np.array(challenges, dtype=np.int8)


def parse_challenges_from_cli(challenge_strings: List[str], challenge_length: int) -> np.ndarray:
    """Parse challenges provided via command line."""
    challenges = []
    for ch_str in challenge_strings:
        ch_str = ch_str.strip()
        if len(ch_str) != challenge_length:
            raise ValueError(f"Challenge length {len(ch_str)} != expected {challenge_length}")
        challenges.append(binary_string_to_challenge(ch_str, challenge_length))
    return np.array(challenges, dtype=np.int8)


def generate_responses_for_challenges(
    puf_name: str,
    puf_params: Dict[str, Any],
    global_config: Dict[str, Any],
    challenges: np.ndarray
) -> pd.DataFrame:
    """Generate responses for user-provided challenges."""
    seed = global_config['seed']
    challenge_length = global_config['challenge_length']
    
    print(f"\nGenerating responses for {len(challenges)} user-provided challenges for {puf_name}...")
    
    # Generate multi-bit responses using multiple PUF instances
    responses = generate_multi_bit_response(puf_name, puf_params, global_config, challenges, seed)
    
    # Convert to binary strings
    challenge_strs = challenges_to_binary_strings(challenges)
    response_strs = responses_to_binary_strings(responses)
    
    # Create DataFrame
    df = pd.DataFrame({
        'challenge': challenge_strs,
        'response': response_strs,
        'puf_type': puf_name
    })
    
    print(f"  Generated {len(df)} responses")
    print(f"  Challenge length: {len(challenge_strs[0])} bits")
    print(f"  Response length: {len(response_strs[0])} bits")
    
    return df


def run_random_mode(global_config: Dict[str, Any], puf_configs: Dict[str, Any], output_dir: Path, puf_type: Optional[str] = None) -> List[pd.DataFrame]:
    """Run the original random challenge generation mode."""
    all_dfs = []
    
    # Determine which PUF types to use
    target_pufs = {puf_type: puf_configs[puf_type]} if puf_type else puf_configs
    
    for puf_name, puf_params in target_pufs.items():
        if not puf_params.get('enabled', False):
            print(f"\nSkipping {puf_name} (disabled)")
            continue
        
        try:
            df = generate_crps_for_puf(puf_name, puf_params, global_config)
            
            # Save individual CSV
            output_file = output_dir / f"{puf_name}_crps.csv"
            df.to_csv(output_file, index=False)
            print(f"  Saved to: {output_file}")
            
            all_dfs.append(df)
            
        except Exception as e:
            print(f"  Error generating CRPs for {puf_name}: {e}")
            import traceback
            traceback.print_exc()
    
    return all_dfs


def generate_crps_for_puf(puf_name: str, puf_params: Dict[str, Any], 
                          global_config: Dict[str, Any]) -> pd.DataFrame:
    """Generate CRPs for a single PUF type with random challenges."""
    num_crp = global_config['num_crp_pairs']
    challenge_length = global_config['challenge_length']
    seed = global_config['seed']
    
    print(f"\nGenerating {num_crp} CRPs for {puf_name}...")
    
    # Generate random challenges
    challenges = random_inputs(n=challenge_length, N=num_crp, seed=seed + hash(puf_name) % 1000)
    
    # Generate multi-bit responses using multiple PUF instances
    responses = generate_multi_bit_response(puf_name, puf_params, global_config, challenges, seed)
    
    # Convert to binary strings
    challenge_strs = challenges_to_binary_strings(challenges)
    response_strs = responses_to_binary_strings(responses)
    
    # Create DataFrame
    df = pd.DataFrame({
        'challenge': challenge_strs,
        'response': response_strs,
        'puf_type': puf_name
    })
    
    print(f"  Generated {len(df)} CRP pairs")
    print(f"  Challenge length: {len(challenge_strs[0])} bits")
    print(f"  Response length: {len(response_strs[0])} bits")
    
    return df


def run_user_challenge_mode(
    global_config: Dict[str, Any],
    puf_configs: Dict[str, Any],
    output_dir: Path,
    challenges: np.ndarray,
    puf_type: Optional[str] = None
) -> List[pd.DataFrame]:
    """Run user-provided challenge mode."""
    all_dfs = []
    
    # Determine which PUF types to use
    target_pufs = {puf_type: puf_configs[puf_type]} if puf_type else puf_configs
    
    for puf_name, puf_params in target_pufs.items():
        if not puf_params.get('enabled', False):
            print(f"\nSkipping {puf_name} (disabled)")
            continue
        
        try:
            df = generate_responses_for_challenges(puf_name, puf_params, global_config, challenges)
            
            # Save individual CSV
            suffix = f"_user" if puf_type else ""
            output_file = output_dir / f"{puf_name}_crps{suffix}.csv"
            df.to_csv(output_file, index=False)
            print(f"  Saved to: {output_file}")
            
            all_dfs.append(df)
            
        except Exception as e:
            print(f"  Error generating responses for {puf_name}: {e}")
            import traceback
            traceback.print_exc()
    
    return all_dfs


def main():
    parser = argparse.ArgumentParser(
        description="PUF CRP Generator - Generate Challenge-Response Pairs for PUFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Random mode (default) - generates random challenges
  uv run python -m PUFForge
  
  # User challenges from file
  uv run python -m PUFForge --challenge-file my_challenges.csv
  
  # User challenges from CLI
  uv run python -m PUFForge --challenges 101010... 010101...
  
  # Single PUF type with user challenges
  uv run python -m PUFForge --challenge-file my_challenges.csv --puf-type xor_arbiter_puf
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.yml',
        help='Path to config.yml (default: config.yml)'
    )
    
    parser.add_argument(
        '--challenge-file', '-f',
        help='CSV file with user-provided challenges (must have "challenge" column)'
    )
    
    parser.add_argument(
        '--challenges',
        nargs='+',
        help='Space-separated list of challenge binary strings (e.g., 101010... 010101...)'
    )
    
    parser.add_argument(
        '--puf-type', '-p',
        help='Specific PUF type to use (default: all enabled PUFs)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        help='Override output directory from config'
    )
    
    parser.add_argument(
        '--list-pufs',
        action='store_true',
        help='List available PUF types and exit'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    global_config = config['global']
    puf_configs = config['pufs']
    
    # Override output dir if provided
    if args.output_dir:
        global_config['output_dir'] = args.output_dir
    
    # List PUF types
    if args.list_pufs:
        print("Available PUF types:")
        for name, params in puf_configs.items():
            status = "enabled" if params.get('enabled', False) else "disabled"
            print(f"  {name}: {status}")
        return
    
    # Create output directory
    output_dir = Path(global_config['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    challenge_length = global_config['challenge_length']
    
    print("=" * 60)
    print("PUF CRP Generator")
    print("=" * 60)
    print(f"Output directory: {output_dir}")
    print(f"Challenge length: {challenge_length} bits")
    print(f"Seed: {global_config['seed']}")
    print("-" * 60)
    
    # Determine mode and load challenges
    if args.challenge_file:
        # Load from file
        print(f"Loading challenges from: {args.challenge_file}")
        try:
            challenges = load_challenges_from_file(args.challenge_file, challenge_length)
            print(f"Loaded {len(challenges)} challenges")
        except Exception as e:
            print(f"Error loading challenges: {e}")
            sys.exit(1)
        
        all_dfs = run_user_challenge_mode(
            global_config, puf_configs, output_dir, challenges, args.puf_type
        )
        
    elif args.challenges:
        # Parse from CLI
        print(f"Parsing {len(args.challenges)} challenges from command line")
        try:
            challenges = parse_challenges_from_cli(args.challenges, challenge_length)
        except Exception as e:
            print(f"Error parsing challenges: {e}")
            sys.exit(1)
        
        all_dfs = run_user_challenge_mode(
            global_config, puf_configs, output_dir, challenges, args.puf_type
        )
        
    else:
        # Random mode (default)
        print(f"Random mode: generating {global_config['num_crp_pairs']} CRPs per PUF")
        all_dfs = run_random_mode(global_config, puf_configs, output_dir, args.puf_type)
    
    # Save combined CSV
    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        combined_file = output_dir / "all_pufs_crps.csv"
        combined_df.to_csv(combined_file, index=False)
        print(f"\nCombined CSV saved to: {combined_file}")
        print(f"Total CRP pairs: {len(combined_df)}")
    
    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()