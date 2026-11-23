<?php
/**
 * Plugin Name: Conclave Elementor cache purge
 * Description: Requests a purge of the host page cache, run at shutdown, when Elementor clears its generated stylesheets, so cached HTML does not keep naming deleted files.
 * Version: 1.0.0
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 *
 * WORKAROUND: Elementor (read in 4.4.1) deletes live stylesheets when it clears its cache, including after an ordinary
 * plugin activation, deactivation or update, and no setting stops it. It rewrites them when PHP next renders a page. The
 * Pressable and WordPress.com page cache does not listen for that, so a page it holds is served with stylesheet links
 * that answer 404. Elementor's "Optimized CSS Files" experiment (alpha) does not stop the deletion, and its internal
 * CSS print method does not reach atomic styles. Remove this file once Elementor keeps files that cached pages name,
 * or the host purges when Elementor clears them.
 *
 * @package Conclave
 */

defined( 'ABSPATH' ) || exit;

// One copy only: a second copy under another name registers nothing twice.
if ( ! defined( 'CONCLAVE_ELEMENTOR_CACHE_PURGE_LOADED' ) ) {
	define( 'CONCLAVE_ELEMENTOR_CACHE_PURGE_LOADED', true );

	/**
	 * Queues one domain purge (Batcache, then the edge) for shutdown through the host's own hook, however often it is called.
	 */
	function conclave_elementor_cache_purge_request() {
		// phpcs:ignore WordPress.NamingConventions.PrefixAllGlobals.NonPrefixedHooknameFound -- a hook the host owns.
		do_action( 'edge_cache_purge_domain' );
	}

	// Every stylesheet is deleted: a plugin or theme change, or a cache clear.
	add_action( 'elementor/core/files/clear_cache', 'conclave_elementor_cache_purge_request', 10, 0 );

	// A style path is cleared: a page, component or global class was saved. A component's stylesheet is named by every page using it.
	add_action(
		'elementor/atomic-widgets/styles/clear',
		static function ( array $path ) {
			// Editor preview styles are never named by a published page.
			if ( in_array( 'preview', $path, true ) ) {
				return;
			}
			// Elementor fires this for every deleted post, styled or not, such as a pruned revision: the host purges a published one.
			if ( isset( $path[1] ) && doing_action( 'deleted_post' ) ) {
				return;
			}
			conclave_elementor_cache_purge_request();
		}
	);
}
