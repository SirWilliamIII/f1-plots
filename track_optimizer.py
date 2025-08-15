"""
Track-Aware Interpolation System for F1 Telemetry

Optimizes telemetry interpolation based on track characteristics.
🔥 NEW: Adaptive resolution based on corner density and track complexity
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from functools import lru_cache


class TrackAwareInterpolator:
    """
    🔥 NEW: Intelligent interpolation system that adapts to track characteristics
    
    Features:
    - Higher resolution near corners, lower on straights
    - Track-specific optimization profiles
    - Caching of track analysis results
    - Performance monitoring and optimization
    """
    
    def __init__(self):
        self.track_profiles = {}
        self.performance_stats = {}
        
        # Track complexity categories
        self.track_categories = {
            'high_complexity': {
                'corner_threshold': 18,
                'base_points': 1200,
                'corner_multiplier': 60,
                'examples': ['Monaco Grand Prix', 'Hungarian Grand Prix', 'Singapore Grand Prix']
            },
            'medium_complexity': {
                'corner_threshold': 12,
                'base_points': 1000,
                'corner_multiplier': 40,
                'examples': ['British Grand Prix', 'Spanish Grand Prix', 'Australian Grand Prix']
            },
            'low_complexity': {
                'corner_threshold': 0,
                'base_points': 800,
                'corner_multiplier': 30,
                'examples': ['Italian Grand Prix', 'Belgian Grand Prix', 'Saudi Arabian Grand Prix']
            }
        }
        
        logging.info("🎯 TrackAwareInterpolator initialized with adaptive algorithms")
    
    def get_track_profile(self, session) -> dict:
        """
        Analyze track characteristics for optimal interpolation
        
        Args:
            session: FastF1 session object
            
        Returns:
            dict: Track profile with optimization parameters
        """
        track_name = session.event['EventName']
        
        # Return cached profile if available
        if track_name in self.track_profiles:
            logging.info(f"📋 Using cached profile for {track_name}")
            return self.track_profiles[track_name]
        
        # Analyze track characteristics
        profile = self._analyze_track_characteristics(session, track_name)
        
        # Cache the profile
        self.track_profiles[track_name] = profile
        logging.info(f"🔍 Analyzed and cached profile for {track_name}: "
                    f"{profile['corner_count']} corners, {profile['optimal_points']} points")
        
        return profile
    
    def _analyze_track_characteristics(self, session, track_name: str) -> dict:
        """Analyze a track's characteristics for interpolation optimization"""
        try:
            circuit_info = session.get_circuit_info()
            
            # Get corner information
            corners = circuit_info.corners if hasattr(circuit_info, 'corners') else []
            corner_count = len(corners)
            
            # Get track length
            try:
                track_length = float(circuit_info.CircuitLength)
            except:
                track_length = 5000.0  # Default fallback
            
            # Determine track category
            category = self._categorize_track(corner_count, track_name)
            category_info = self.track_categories[category]
            
            # Calculate optimal points
            optimal_points = self._calculate_optimal_points(corner_count, category_info)
            
            # Build profile
            profile = {
                'name': track_name,
                'corner_count': corner_count,
                'total_distance': track_length,
                'category': category,
                'optimal_points': optimal_points,
                'corner_zones': [],
                'straight_zones': [],
                'corner_density': corner_count / (track_length / 1000),  # corners per km
                'analysis_timestamp': time.time()
            }
            
            # Analyze corner zones if corner data available
            if len(corners) > 0:
                profile['corner_zones'] = self._identify_corner_zones(corners, track_length)
                profile['straight_zones'] = self._identify_straight_zones(profile['corner_zones'], track_length)
            
            return profile
            
        except Exception as e:
            logging.warning(f"Failed to analyze {track_name}: {e}")
            return self._get_fallback_profile(track_name)
    
    def _categorize_track(self, corner_count: int, track_name: str) -> str:
        """Categorize track based on complexity"""
        
        # Check if track is in predefined categories
        for category, info in self.track_categories.items():
            if track_name in info['examples']:
                return category
        
        # Categorize based on corner count
        if corner_count >= self.track_categories['high_complexity']['corner_threshold']:
            return 'high_complexity'
        elif corner_count >= self.track_categories['medium_complexity']['corner_threshold']:
            return 'medium_complexity'
        else:
            return 'low_complexity'
    
    def _calculate_optimal_points(self, corner_count: int, category_info: dict) -> int:
        """Calculate optimal interpolation points for a track"""
        base_points = category_info['base_points']
        corner_bonus = corner_count * category_info['corner_multiplier']
        
        # Apply limits
        optimal_points = min(2500, max(600, base_points + corner_bonus))
        
        return optimal_points
    
    def _identify_corner_zones(self, corners, track_length: float) -> List[Tuple[float, float]]:
        """Identify corner zones requiring high-resolution interpolation"""
        corner_zones = []
        
        for _, corner in corners.iterrows():
            corner_distance = corner['Distance']
            
            # Define corner zone with buffer (±75m for tight corners, ±50m for fast corners)
            # This is a simplified approach - could be enhanced with corner speed analysis
            buffer = 75.0  # meters
            
            start_dist = max(0, corner_distance - buffer)
            end_dist = min(track_length, corner_distance + buffer)
            
            corner_zones.append((start_dist, end_dist))
        
        # Merge overlapping corner zones
        corner_zones = self._merge_overlapping_zones(corner_zones)
        
        return corner_zones
    
    def _identify_straight_zones(self, corner_zones: List[Tuple], track_length: float) -> List[Tuple[float, float]]:
        """Identify straight sections between corners"""
        if not corner_zones:
            return [(0, track_length)]
        
        straight_zones = []
        
        # Add straight before first corner
        if corner_zones[0][0] > 0:
            straight_zones.append((0, corner_zones[0][0]))
        
        # Add straights between corners
        for i in range(len(corner_zones) - 1):
            straight_start = corner_zones[i][1]
            straight_end = corner_zones[i + 1][0]
            
            if straight_end > straight_start:
                straight_zones.append((straight_start, straight_end))
        
        # Add straight after last corner
        if corner_zones[-1][1] < track_length:
            straight_zones.append((corner_zones[-1][1], track_length))
        
        return straight_zones
    
    def _merge_overlapping_zones(self, zones: List[Tuple]) -> List[Tuple]:
        """Merge overlapping distance zones"""
        if not zones:
            return []
        
        # Sort zones by start distance
        zones.sort(key=lambda x: x[0])
        
        merged = [zones[0]]
        
        for current in zones[1:]:
            last_merged = merged[-1]
            
            # If zones overlap, merge them
            if current[0] <= last_merged[1]:
                merged[-1] = (last_merged[0], max(last_merged[1], current[1]))
            else:
                merged.append(current)
        
        return merged
    
    def _get_fallback_profile(self, track_name: str) -> dict:
        """Get fallback profile when analysis fails"""
        return {
            'name': track_name,
            'corner_count': 15,  # Average
            'total_distance': 5000.0,  # Average
            'category': 'medium_complexity',
            'optimal_points': 1200,
            'corner_zones': [],
            'straight_zones': [],
            'corner_density': 3.0,  # corners per km
            'analysis_timestamp': time.time(),
            'fallback': True
        }
    
    def create_adaptive_distance_array(self, min_dist: float, max_dist: float, 
                                     track_profile: dict) -> np.ndarray:
        """
        🔥 NEW: Create adaptive distance array with variable resolution
        
        Higher density near corners, optimized spacing on straights
        """
        corner_zones = track_profile['corner_zones']
        total_distance = max_dist - min_dist
        target_points = track_profile['optimal_points']
        
        # If no corner zones identified, use linear spacing
        if not corner_zones:
            logging.info(f"📏 Using linear spacing: {target_points} points")
            return np.linspace(min_dist, max_dist, target_points)
        
        # Create adaptive points array
        adaptive_points = []
        current_dist = min_dist
        points_used = 0
        
        # Calculate distance budgets
        corner_distance = sum(end - start for start, end in corner_zones 
                            if start >= min_dist and end <= max_dist)
        straight_distance = total_distance - corner_distance
        
        # Allocate points: 70% for corners, 30% for straights
        corner_points_budget = int(target_points * 0.7)
        straight_points_budget = target_points - corner_points_budget
        
        # Calculate step sizes
        corner_step = corner_distance / max(1, corner_points_budget) if corner_distance > 0 else 2.0
        straight_step = straight_distance / max(1, straight_points_budget) if straight_distance > 0 else 8.0
        
        # Generate adaptive points
        while current_dist < max_dist and points_used < target_points:
            adaptive_points.append(current_dist)
            
            # Determine if we're in a corner zone
            in_corner = any(start <= current_dist <= end for start, end in corner_zones)
            
            # Use appropriate step size
            step_size = min(corner_step, 2.0) if in_corner else min(straight_step, 10.0)
            current_dist += step_size
            points_used += 1
        
        # Ensure we end at max_dist
        if adaptive_points and adaptive_points[-1] < max_dist:
            adaptive_points.append(max_dist)
        
        result = np.array(adaptive_points[:target_points])
        
        logging.info(f"🎯 Created adaptive array: {len(result)} points, "
                    f"corner step ~{corner_step:.1f}m, straight step ~{straight_step:.1f}m")
        
        return result
    
    def get_interpolation_performance_stats(self, track_name: str) -> dict:
        """Get performance statistics for a specific track"""
        return self.performance_stats.get(track_name, {})
    
    def record_interpolation_performance(self, track_name: str, points_used: int, 
                                       processing_time: float, accuracy_estimate: float = None):
        """Record performance statistics for optimization"""
        if track_name not in self.performance_stats:
            self.performance_stats[track_name] = {
                'interpolations_count': 0,
                'total_processing_time': 0,
                'average_points': 0,
                'accuracy_estimates': []
            }
        
        stats = self.performance_stats[track_name]
        stats['interpolations_count'] += 1
        stats['total_processing_time'] += processing_time
        stats['average_points'] = ((stats['average_points'] * (stats['interpolations_count'] - 1)) + points_used) / stats['interpolations_count']
        
        if accuracy_estimate is not None:
            stats['accuracy_estimates'].append(accuracy_estimate)
        
        # Log performance milestone
        if stats['interpolations_count'] % 10 == 0:
            avg_time = stats['total_processing_time'] / stats['interpolations_count']
            logging.info(f"📊 {track_name} interpolation stats: "
                        f"{stats['interpolations_count']} runs, "
                        f"avg {avg_time:.2f}s, {stats['average_points']:.0f} points")
    
    @lru_cache(maxsize=20)
    def get_track_optimization_recommendations(self, track_name: str) -> dict:
        """Get optimization recommendations for a specific track"""
        profile = self.track_profiles.get(track_name)
        if not profile:
            return {}
        
        recommendations = {
            'recommended_points': profile['optimal_points'],
            'complexity_category': profile['category'],
            'optimization_focus': [],
            'expected_performance': {}
        }
        
        # Add specific recommendations based on track characteristics
        if profile['category'] == 'high_complexity':
            recommendations['optimization_focus'].extend([
                'Use high resolution near corners',
                'Consider sector-specific optimization',
                'Monitor memory usage closely'
            ])
            recommendations['expected_performance'] = {
                'processing_time': 'Higher (complex track)',
                'accuracy': 'Excellent in corners',
                'memory_usage': 'High'
            }
        elif profile['category'] == 'low_complexity':
            recommendations['optimization_focus'].extend([
                'Reduce straight-line sampling',
                'Focus resolution on few key corners',
                'Optimize for speed over precision'
            ])
            recommendations['expected_performance'] = {
                'processing_time': 'Lower (simple track)',
                'accuracy': 'Good overall',
                'memory_usage': 'Low'
            }
        
        return recommendations


# Convenience function for backward compatibility
def create_optimized_distance_array(session, drv1_tel, drv2_tel, interpolator=None):
    """
    Create optimized distance array for telemetry interpolation
    
    Args:
        session: FastF1 session object
        drv1_tel: Driver 1 telemetry data
        drv2_tel: Driver 2 telemetry data
        interpolator: TrackAwareInterpolator instance (optional)
    
    Returns:
        np.ndarray: Optimized distance array
    """
    if interpolator is None:
        interpolator = TrackAwareInterpolator()
    
    # Get track profile
    track_profile = interpolator.get_track_profile(session)
    
    # Determine distance range
    min_dist = max(drv1_tel["Distance"].min(), drv2_tel["Distance"].min())
    max_dist = min(drv1_tel["Distance"].max(), drv2_tel["Distance"].max())
    
    # Create adaptive array
    return interpolator.create_adaptive_distance_array(min_dist, max_dist, track_profile)


# Global interpolator instance for reuse
global_interpolator = TrackAwareInterpolator()
